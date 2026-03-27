import logging
import re
from src.tools.connect_tool import command_batch as subprocess
import time, platform
import os, csv, threading
import json
import pytest
from pathlib import Path
from collections import defaultdict
from src.tools.relay_tool.pdusnmp import power_ctrl
from src.tools.router_tool.Router import Router
from src.tools.router_tool.router_performance import (
    FPGA_CONFIG,
    compatibility_router,
    handle_expectdata as perf_handle_expectdata,
)
from src.util.constants import load_config
from src.tools.relay_tool.pdusnmp import power_ctrl as PduSnmpCtrl
from src.util.constants import load_config
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin

_ap_test_state = {}
_ap_test_lock = threading.Lock()
_test_metadata_cache = {}
_metadata_lock = threading.Lock()
_str_result_lock = threading.Lock()
_str_test_results = defaultdict(dict)

power_delay = power_ctrl()
# power_delay.shutdown()
power_ctrl = power_delay.ctrl
router = ''

ssid = {
     #'2.4G': 'Aml_AP_Comp_2.4G',
     #'5G': 'Aml_AP_Comp_5G'
    '2.4G': 'AX88U_24G',
    '5G': 'AX88U_5G'
}
ssid_6g = 'Aml_AP_Comp_6G'
#passwd = '@Aml#*st271'
passwd = '88888888'

#AP_REBOOT_ROUNDS = 1  # 可设为 1, 2, 3...

# Project and chip info
project_cfg = pytest.config.get("project") or {}
wifi_module = str(project_cfg.get("wifi_module", "")).strip().upper()
interface = str(project_cfg.get("interface", "")).strip().upper()
pytest.chip_info = f"{wifi_module}_{interface}" if wifi_module or interface else ""
customer = str(project_cfg.get("customer", "")).strip()
project_name = str(project_cfg.get("name", "")).strip()
project_id = str(project_cfg.get("project", "")).strip()
cfg = load_config(refresh=True)
raw_loop = (cfg.get("duration_control", {})).get("loop", 0)
try:
    AP_REBOOT_ROUNDS = int(raw_loop)
except (ValueError, TypeError):
    logging.warning(f"Invalid 'loop' value in config: {raw_loop}. Defaulting to 1.")
    AP_REBOOT_ROUNDS = 1


# Avoid shutting down power at import time; defer to fixture lifecycle.
@pytest.fixture(scope="session", autouse=True)
def initialize_all_relays():
    """ 🚫 在 compatibility 测试会话开始前，将所有 relay ports 断电。 仅当运行本文件中的测试时才会触发。 """
    # 获取所有 relay 列表
    logging.info("[COMPAT] Powering OFF all relay ports before compatibility tests...")
    temp = PduSnmpCtrl()
    all_relays = temp.ctrl
    temp.shutdown()
    return "PDU initialized"


@pytest.fixture(scope='module', autouse=True, params=power_ctrl, ids=[str(i) for i in power_ctrl])
def power_setting(request):
    ip, port = request.param
    try:
        power_delay.switch(ip, port, 1)
        time.sleep(30)
        info = [
            x for x in filter(
                lambda x: str(x.get('port')) == str(port) and x.get('ip') == ip,
                compatibility_router._instances,
            )
        ]
        if not info:
            raise RuntimeError(f"Router info not found for ip={ip} port={port}")
        current_ap_key = f"{ip}:{port}"
        pytest.current_target_ap = current_ap_key
        yield info[0]
    finally:
        logging.info('test done shutdown the router')
        power_delay.switch(ip, port, 2)


@pytest.fixture(scope='module', autouse=True) #, params=['2.4G', '5G'], ids=['2.4G', '5G']
def router_setting(power_setting, request):
    #band = request.param
    if not power_setting:
        raise ValueError("Pls check pdu ip address and router port")

    current_ap_key = getattr(pytest, 'current_target_ap', 'unknown_ap')
    # --- 【关键】从全局缓存中读取 *当前 AP* 的已知 IP ---
    # 我们用一个字典来存储每个 AP 的有效 IP
    ap_ip_cache = getattr(pytest, '_ap_ip_cache', {})
    last_known_ip_for_this_ap = ap_ip_cache.get(current_ap_key)
    pc_ip = None
    # 获取上一个 AP 的 IP，用于对比
    last_tested_ap = getattr(pytest, '_last_tested_ap', None)
    last_ap_ip = ap_ip_cache.get(last_tested_ap) if last_tested_ap else None

    if last_known_ip_for_this_ap:
        pc_ip = last_known_ip_for_this_ap
        logging.info(f"Reusing cached PC IP for AP {current_ap_key}: {pc_ip}")
    else:
        try:
            nic = load_config(refresh=True).get("compatibility", {}).get("nic") or "eth1"
        except Exception:
            nic = "eth1"

        max_retries = 3
        current_retry = 0
        pc_ip = "192.168.50.77"  #None

        # while current_retry < max_retries:
        #     current_retry += 1
        #     pc_ip = pytest.host_os.dynamic_flush_network_card(nic)
        #     #pc_ip = "192.168.50.77"
        #
        #     if pc_ip is None:
        #         if current_retry < max_retries:
        #             time.sleep(5)
        #         continue
        #
        #     # --- 【核心逻辑】---
        #     # 对于 *同一个 AP*，如果已经有一个有效的 IP，并且新拿到的 IP 和它一样，
        #     # 这是完全正常的！直接接受。
        #     if last_known_ip_for_this_ap and pc_ip == last_known_ip_for_this_ap:
        #         break
        #
        #     if last_ap_ip and pc_ip == last_ap_ip:
        #         logging.warning(
        #             f"Network may not have switched! Retrying..."
        #         )
        #         if current_retry < max_retries:
        #             time.sleep(5)
        #         continue
        #
        #     break
        #
        # else:
        #     pytest.fail(f"Failed to get PC IP for AP {current_ap_key}.")

    # --- 【关键】将有效的 IP 缓存到 *当前 AP* 的名下 ---
    ap_ip_cache[current_ap_key] = pc_ip
    pytest._ap_ip_cache = ap_ip_cache
    pytest._last_tested_ap = current_ap_key
    pytest.dut.pc_ip = pc_ip
    #logging.info(f'✅ [{band}] PC IP for {current_ap_key}: {pc_ip}')
    logging.info(f'pc_ip {pytest.dut.pc_ip}')

    #logging.info(f'✅ [{band}] PC IP for {current_ap_key}: {pc_ip}')

    logging.info(f'pc_ip {pytest.dut.pc_ip}')
    router_set = power_setting
    return power_setting
    # expect_tx = perf_handle_expectdata(router_set, band, 'UL', pytest.chip_info)
    # expect_rx = perf_handle_expectdata(router_set, band, 'DL', pytest.chip_info)
    # router_obj = Router(
    #     band=band,
    #     wireless_mode=router_set[band]['mode'],
    #     channel='default',
    #     security_mode=router_set[band].get('security_mode'),
    #     bandwidth=router_set[band]['bandwidth'],
    #     ssid=ssid[band],
    #     password=passwd,
    #     expected_rate=f'{expect_tx} {expect_rx}',
    # )
    # logging.info(f'router yield {router_obj}')
    # yield router_obj


# ========================
# 【新增】主测试函数：单函数内循环处理多轮
# ========================
def test_wifi_reconnect_full_flow(power_setting):
    """ 执行完整的 AP 重启重连测试流程。 执行顺序：AP1 → 2.4G: R0→R1→...→RN; AP1 → 5G: R0→R1→...→RN """
    any_fatal_error = False
    pdu_ip = power_setting['ip']
    pdu_port = power_setting['port']
    current_ap_key = f"{pdu_ip}:{pdu_port}"

    cfg = load_config(refresh=True)
    dut_serial = cfg.get("connect_type", {}).get("Android", {}).get("device")
    if not dut_serial:
        pytest.fail("Failed to get DUT serial from config for reboot.")
    logging.info(f"Using DUT serial: {dut_serial}")

    try:
        # 遍历频段：先 2.4G，再 5G
        for band in ['2.4G', '5G']:
            logging.info(f"📡 Starting full sequence for AP {current_ap_key}, Band: {band}")

            # 构建 Router 对象
            expect_tx = perf_handle_expectdata(power_setting, band, 'UL', pytest.chip_info)
            expect_rx = perf_handle_expectdata(power_setting, band, 'DL', pytest.chip_info)
            router_obj = Router(
                band=band,
                wireless_mode=power_setting[band]['mode'],
                channel='default',
                security_mode=power_setting[band].get('security_mode'),
                bandwidth=power_setting[band]['bandwidth'],
                ssid=ssid[band],
                password=passwd,
                expected_rate=f'{expect_tx} {expect_rx}',
            )

            # --- 初始化 CSV 状态：为每一轮创建独立条目 ---
            for round_index in range(AP_REBOOT_ROUNDS):
                key = (pdu_ip, pdu_port, band, round_index)
                with _str_result_lock:
                    if key not in _str_test_results:
                        _str_test_results[key] = {
                            "ap_brand": f"{power_setting.get('brand', '')} {power_setting.get('model', '')}".strip() or "Unknown",
                            "ssid": router_obj.ssid,
                            "wifi_mode": router_obj.wireless_mode,
                            "bandwidth": router_obj.bandwidth,
                            "security": router_obj.security_mode or "open",
                            "round": f"Round {round_index + 1}",
                            "scan": "N/A",
                            "connect": "N/A",
                            "ping": "N/A",
                            "tx_channel": "N/A",
                            "tx_rssi": "N/A",
                            "tx_throughput": "N/A",
                            "rx_channel": "N/A",
                            "rx_rssi": "N/A",
                            "rx_throughput": "N/A",
                            "reconnection_time": "N/A",
                        }

            # ========================
            # 执行所有轮次 (0 到 N-1)
            # ========================
            for round_index in range(AP_REBOOT_ROUNDS):
                logging.info(f"🔄 AP {current_ap_key} | {band} | Round {round_index + 1}/{AP_REBOOT_ROUNDS}")
                reconnection_time = None

                if round_index == 0:
                    # --- Round 0: 初始连接 ---
                    logging.info("→ Round 0: Initial connection (Scan → Connect)")
                    pytest.dut.wifi_forget()

                    # --- Scan ---
                    scan_pass = False
                    try:
                        if pytest.connect_type == 'Linux':
                            if not pytest.dut.flush_ip():
                                raise Exception("flush_ip failed")
                        #scan_pass = pytest.dut.wifi_scan(router_obj.ssid)
                        scan_pass = pytest.dut.wifi_scan(ssid[band])
                    except Exception as e:
                        logging.error(f"Scan failed in round {round_index}: {e}")
                    scan_result = "PASS" if scan_pass else "FAIL"

                    if scan_result != "PASS":
                        logging.error(f"Scan failed for {band} in round {round_index}. Skipping the entire band.")
                        any_fatal_error = True
                        # 更新 Round 0 的状态
                        with _str_result_lock:
                            _str_test_results[(pdu_ip, pdu_port, band, 0)].update({
                                "scan": scan_result,
                                "connect": "FAIL",
                            })
                        # === 关键：跳过整个频段 ===
                        break  # 使用 break 跳出当前 band 的轮次循环

                    # --- Connect ---
                    pytest.dut.wifi_connect(
                        #router_obj.ssid, password=router_obj.password, security=router_obj.security_mode,
                        ssid[band], password=passwd, security=router_obj.security_mode,
                    )
                    connected = False
                    dut_ip_addr = None
                    try:
                        connected, dut_ip_addr = pytest.dut.wifi_wait_ip(timeout_s=120)
                        if connected and dut_ip_addr:
                            pytest.dut.dut_ip = dut_ip_addr
                            pytest.dut.get_rssi()
                    except Exception as e:
                        logging.error(f"DUT failed to connect in Round 0 for {band}! Error: {e}")

                    if not connected:
                        logging.error(f"DUT failed to connect in Round 0 for {band}! Skipping the entire band.")
                        any_fatal_error = True
                        # 更新 Round 0 的状态
                        with _str_result_lock:
                            _str_test_results[(pdu_ip, pdu_port, band, 0)].update({
                                "scan": scan_result,
                                "connect": "FAIL",
                            })
                        # === 关键：跳过整个频段 ===
                        break  # 使用 break 跳出当前 band 的轮次循环

                else:
                    # --- Round N (N>0): 重启 AP 并等待重连 ---
                    logging.info(f"→ Round {round_index}: Reboot AP and wait for auto-reconnect")
                    # 重启 AP
                    power_delay.switch(pdu_ip, pdu_port, 2)
                    time.sleep(10)
                    power_on_time = time.time()
                    power_delay.switch(pdu_ip, pdu_port, 1)
                    time.sleep(30)

                    # --- 等待 DUT 自动重连 ---
                    logging.info("→ Waiting for DUT to reconnect automatically...")
                    connected = False
                    dut_ip_addr = None
                    reconnection_time = None
                    try:
                        connected, dut_ip_addr = pytest.dut.wifi_wait_ip(timeout_s=300)
                        if connected and dut_ip_addr:
                            pytest.dut.dut_ip = dut_ip_addr
                            reconnection_time = time.time() - power_on_time
                            logging.info(f"⏱️ DUT reconnected in {reconnection_time:.2f} seconds")
                            pytest.dut.get_rssi()
                    except Exception as e:
                        logging.error(
                            f"DUT failed to reconnect after AP reboot in Round {round_index} for {band}! Error: {e}")
                        reconnection_time = time.time() - power_on_time

                # --- Connect 验证 (频段等) ---
                connect_pass = True
                try:
                    if not getattr(pytest.dut, 'dut_ip', None):
                        connect_pass = False
                    if band == '5G' and not (getattr(pytest.dut, 'freq_num', 0) > 5000):
                        connect_pass = False
                    if band == '2.4G' and not (getattr(pytest.dut, 'freq_num', 0) < 5000):
                        connect_pass = False
                except Exception as e:
                    logging.error(f"Connect validation error: {e}")
                    connect_pass = False
                connect_result = "PASS" if connect_pass else "FAIL"

                if connect_result != "PASS":
                    any_fatal_error = True

                # === 在 EVERY ROUND (包括 Round 0) 都执行 Ping 和打流 ===
                # --- Ping 验证 ---
                if not connected:
                    logging.warning(f"Skipping Ping for {band} Round {round_index + 1} because DUT is not connected.")
                    ping_result = "SKIP"
                else:
                    ping_success = _perform_ping_test()
                    ping_result = "PASS" if ping_success else "FAIL"

                # --- Throughput 测试 ---
                if not connected:
                    logging.warning(
                        f"Skipping Throughput test for {band} Round {round_index + 1} because DUT is not connected.")
                    tx_result = "SKIP"
                    rx_result = "SKIP"
                else:
                    tx_result = "N/A"
                    rx_result = "N/A"
                    if customer == "ONN" or project_name == "KitKat513" or project_id == "KitKat513":
                        tx_result = "SKIP"
                        rx_result = "SKIP"
                    else:
                        try:
                            tx_result = pytest.dut.get_tx_rate(router_obj, pytest.dut.rssi_num)
                            rx_result = pytest.dut.get_rx_rate(router_obj, pytest.dut.rssi_num)
                        except Exception as e:
                            logging.error(f"Throughput error (non-fatal): {e}")
                            tx_result = "ERROR"
                            rx_result = "ERROR"

                # --- 更新当前轮次的状态 ---
                round_key = (pdu_ip, pdu_port, band, round_index)
                with _str_result_lock:
                    state = _str_test_results[round_key]
                    # Round 0 需要记录 Scan 结果
                    scan_to_record = scan_result if round_index == 0 else "N/A"
                    state.update({
                        "scan": scan_to_record,
                        "connect": connect_result,
                        "ping": ping_result,
                        "tx_throughput": tx_result,
                        "rx_throughput": rx_result,
                        "tx_channel": getattr(pytest.dut, 'channel', "N/A"),
                        "tx_rssi": getattr(pytest.dut, 'rssi_num', "N/A"),
                        "rx_channel": getattr(pytest.dut, 'channel', "N/A"),
                        "rx_rssi": getattr(pytest.dut, 'rssi_num', "N/A"),
                        "reconnection_time": f"{reconnection_time:.2f}" if reconnection_time else "N/A",
                    })

                # === 每轮结束后立即写入 CSV ===
                report_dir = os.environ.get("PYTEST_REPORT_DIR")
                if report_dir:
                    try:
                        _write_ap_reboot_str_csv(report_dir)
                        logging.info(f"✅ Round {round_index + 1} data written to CSV.")
                    except Exception as write_e:
                        logging.error(f"Failed to write CSV after round {round_index}: {write_e}")

        # === 在所有测试完成后，统一检查是否有致命错误 ===
        if any_fatal_error:
            pytest.fail("One or more critical steps (Scan/Connect) failed during the test.")

    finally:
        # 清理工作已在 fixture 的 finally 块中完成
        pass

# ========================
# 辅助函数：Ping 测试
# ========================
def _perform_ping_test():
    if not getattr(pytest.dut, 'dut_ip', None):
        return False
    if not getattr(pytest.dut, 'pc_ip', None):
        return False

    dut_ip = pytest.dut.dut_ip
    logging.info(f"Pinging DUT({dut_ip})")

    if platform.system() == "Windows":
        cmd = f"ping -n 60 -w 1000 {dut_ip}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=False)
        #logging.info(f"Ping Base Result: '{result}'")

        # === 直接使用 stdout，无需 decode ===
        output = result.stdout
        logging.info(f"Ping Result: '{output}'")

        # === 精准解析你的日志格式 ===
        lost_count = None

        # 方案1: 匹配乱码 "ʧ = 数字"
        loss_match = re.search(r'ʧ\s*[=:：]?\s*(\d+)', output)
        if loss_match:
            lost_count = int(loss_match.group(1))

        # 方案2: 匹配标准中文 "丢失 = 数字"
        if lost_count is None:
            loss_match = re.search(r'丢失\s*[=:：]?\s*(\d+)', output)
            if loss_match:
                lost_count = int(loss_match.group(1))

        # === 判定结果 ===
        if lost_count is not None:
            success = (lost_count == 0)
        else:
            # 如果还是无法解析，保守地认为只要命令执行成功就算通
            success = (result.returncode == 0)

        return success

    else:
        # Linux
        cmd = f"ping -c 60 -W 1 {dut_ip}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = result.stdout
        match = re.search(r'(\d+)%\s+packet\s+loss', output)
        lost = int(int(match.group(1)) * 60 / 100) if match else None

    success = (lost == 0) if lost is not None else (result.returncode == 0)
    return success


# ========================
# 保留原有 CSV 写入函数
# ========================
def _write_ap_reboot_str_csv(report_dir: str):
    """Write AP_Reboot_STR.csv from internal _str_test_results."""
    rows = []
    with _str_result_lock:
        for key, state in _str_test_results.items():
            ip, port, band, round_index = key # 解包新的 key
            row = [
                ip,
                port,
                state["ap_brand"],
                band,
                state["round"], # 新增 Round 列
                state["ssid"],
                state["wifi_mode"],
                state["bandwidth"],
                state["security"],
                state["scan"],
                state["connect"],
                state["ping"],
                state["tx_channel"],
                state["tx_rssi"],
                state["tx_throughput"],
                state["rx_channel"],
                state["rx_rssi"],
                state["rx_throughput"],
                state["reconnection_time"]
            ]
            rows.append(row)
    # 排序：按 IP, Port, Band, Round
    rows.sort(key=lambda x: (x[0], x[1], x[3], x[4]))
    csv_path = Path(report_dir) / "AP_Reboot_STR.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "PDU IP", "PDU Port", "AP Brand", "Band", "Round", # 新增 Round 列头
            "Ssid", "WiFi Mode", "Bandwidth", "Security",
            "Scan", "Connect", "Ping",
            "Channel(TX)", "RSSI(TX)", "TX Throughtput(Mbps)",
            "Channel(RX)", "RSSI(RX)", "RX Throughtput(Mbps)",
            "Reconnection Time (s)"
        ])
        writer.writerows(rows)
    logging.info(f"✅ Wrote AP_Reboot_STR.csv to {csv_path}")