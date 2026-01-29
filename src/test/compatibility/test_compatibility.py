import logging
import re
from src.tools.connect_tool import command_batch as subprocess
import time, platform
import os, csv, threading
import json
import pytest
from pathlib import Path

from src.tools.relay_tool.pdusnmp import power_ctrl
from src.tools.router_tool.Router import Router
from src.tools.router_tool.router_performance import (
    FPGA_CONFIG,
    compatibility_router,
    handle_expectdata as perf_handle_expectdata,
)
from src.util.constants import load_config
from src.tools.relay_tool.pdusnmp import power_ctrl as PduSnmpCtrl

_ap_test_state = {}
_ap_test_lock = threading.Lock()
_test_metadata_cache = {}
_metadata_lock = threading.Lock()


power_delay = power_ctrl()
# power_delay.shutdown()
power_ctrl = power_delay.ctrl
router = ''
ssid = {
    '2.4G': 'Aml_AP_Comp_2.4G',
    '5G': 'Aml_AP_Comp_5G'
}
ssid_6g = 'Aml_AP_Comp_6G'
passwd = '@Aml#*st271'

# Project and chip info
project_cfg = pytest.config.get("project") or {}
wifi_module = str(project_cfg.get("wifi_module", "")).strip().upper()
interface = str(project_cfg.get("interface", "")).strip().upper()
pytest.chip_info = f"{wifi_module}_{interface}" if wifi_module or interface else ""
customer = str(project_cfg.get("customer", "")).strip()
project_name = str(project_cfg.get("name", "")).strip()
project_id = str(project_cfg.get("project", "")).strip()
# Avoid shutting down power at import time; defer to fixture lifecycle.

@pytest.fixture(scope="session", autouse=True)
def initialize_all_relays():
    """
    🚫 在 compatibility 测试会话开始前，将所有 relay ports 断电。
    仅当运行本文件中的测试时才会触发。
    """
    # 获取所有 relay 列表
    temp = PduSnmpCtrl()
    all_relays = temp.ctrl
    temp.shutdown()

    logging.info("🔌 [COMPAT] Powering OFF all relay ports before compatibility tests...")
    for ip, port in all_relays:
        pdu = PduSnmpCtrl()
        try:
            pdu.switch(ip, port, 0)  # 断电
            logging.info(f"  → OFF: {ip}:{port}")
        finally:
            if hasattr(pdu, 'shutdown'):
                pdu.shutdown()
    logging.info("✅ All relays powered OFF. Ready for compatibility testing.")
    return "PDU initialized"

@pytest.fixture(scope='module', autouse=True, params=power_ctrl, ids=[str(i) for i in power_ctrl])
def power_setting(request):
    ip, port = request.param
    try:
        power_delay.switch(ip, port, 1)
        time.sleep(30)
        info = [
            x
            for x in filter(
                lambda x: str(x.get('port')) == str(port) and x.get('ip') == ip,
                compatibility_router._instances,
            )
        ]
        if not info:
            raise RuntimeError(f"Router info not found for ip={ip} port={port}")
        yield info[0]
    finally:
        logging.info('test done shutdown the router')
        power_delay.switch(ip, port, 2)



@pytest.fixture(scope='module', autouse=True, params=['2.4G', '5G'], ids=['2.4G', '5G'])
def router_setting(power_setting, request):
    if not power_setting:
        raise ValueError("Pls check pdu ip address and router port")
    try:
        nic = load_config(refresh=True).get("compatibility", {}).get("nic") or "eth1"
    except Exception:
        nic = "eth1"
    pytest.dut.pc_ip = pytest.host_os.dynamic_flush_network_card(nic)
    if pytest.dut.pc_ip is None:
        error_msg = f"Can't get PC IP address on NIC: {nic}"
        logging.error(error_msg)
        request.node._store['return_value'] = ("N/A", "N/A", "N/A", "FAIL")
        request.node._store['compat_compare'] = "FAIL"
        pytest.fail(f"PC can't get  IP address ")

        assert False, "Can't get pc ip address"

    logging.info(f'pc_ip {pytest.dut.pc_ip}')
    router_set = power_setting
    band = request.param
    expect_tx = perf_handle_expectdata(router_set, band, 'UL', pytest.chip_info)
    expect_rx = perf_handle_expectdata(router_set, band, 'DL', pytest.chip_info)
    router_obj = Router(
        band=band,
        wireless_mode=router_set[band]['mode'],
        channel='default',
        security_mode=router_set[band].get('security_mode'),
        bandwidth=router_set[band]['bandwidth'],
        ssid=ssid[band],
        password=passwd,
        expected_rate=f'{expect_tx} {expect_rx}',
    )
    logging.info(f'router yield {router_obj}')
    yield router_obj


@pytest.mark.dependency(name="scan")
def test_scan(router_setting, request):
    result = 'FAIL'
    try:
        if pytest.connect_type == 'Linux':
            result = 'PASS' if pytest.dut.flush_ip() else 'FAIL'
            assert result =='PASS',f"Can't be reconnected"
            logging.info(f'dut_ip: {pytest.dut.dut_ip}')
        # pytest.dut.push_iperf()
        result = 'PASS' if pytest.dut.wifi_scan(router_setting.ssid) else 'FAIL'

    except Exception as e:
        logging.error(f"Scan failed: {e}")
        # failed and record891a80fdb51f230438d52f26a19845523a0b05c1
        request.node._store['return_value'] = ("N/A", "N/A", "N/A", "FAIL")
        request.node._store['compat_compare'] = "FAIL"
        pytest.fail(f"Scan test failed: {e}")

    assert result == 'PASS', f"Can't scan target ssid {router_setting.ssid}"


@pytest.mark.dependency(name="connect", depends=["scan"])
def test_connect(router_setting, request):
    result = 'FAIL'
    print(">>> ENTERING test_connect!")
    try:
        pytest.dut.wifi_forget()
        pytest.dut.wifi_connect(
            router_setting.ssid,
            password=router_setting.password,
            security=router_setting.security_mode,
        )
        result = 'PASS' if pytest.dut.wifi_wait_ip()[0] else 'FAIL'
        pytest.dut.get_rssi()
        if router_setting.band == '5G':
            assert pytest.dut.freq_num > 5000
        if router_setting.band == '2.4G':
            assert pytest.dut.freq_num < 5000
        # Update channel attribute directly for downstream tests.
        try:
            router_setting.channel = pytest.dut.channel
        except Exception:
            pass

    except Exception as e:
        logging.error(f"Connection failed: {e}")
        # failed and record
        ch = getattr(pytest.dut, 'channel', 'N/A')
        rssi = getattr(pytest.dut, 'rssi_num', 'N/A')
        request.node._store["return_value"] = (ch, rssi, "N/A", "FAIL")
        request.node._store['compat_compare'] = "FAIL"
        pytest.fail(f"Connect test failed: {e}")

    assert result == 'PASS', "Can't connect ssid"
    logging.info("✅ test_scan PASSED successfully!")

@pytest.mark.dependency(depends=["connect"])
def test_ping(router_setting, request):
    """Verify PC can ping DUT for 60 seconds with 0% packet loss."""
    if not getattr(pytest.dut, 'pc_ip', None):
        assert False, "PC IP not available"
    if not getattr(pytest.dut, 'dut_ip', None):
        assert False, "DUT IP not available (check test_connect)"

    pc_ip = pytest.dut.pc_ip
    dut_ip = pytest.dut.dut_ip
    current_os = platform.system()
    logging.info(f"Verifying connectivity: PC({pc_ip}) -> DUT({dut_ip})")

    if platform.system() == "Windows":
        cmd = f"ping -n 60 -w 1000 {dut_ip}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=False)

        output = result.stdout
        logging.info(f"Ping Result: '{output}'")

        # 先尝试中文，再尝试英文
        match = re.search(r'丢失\s*[=:：]\s*(\d+)', output)
        if not match:
            match = re.search(r'Lost\s*[=:]\s*(\d+)', output, re.IGNORECASE)

        lost = int(match.group(1)) if match else None
    else:
        # Linux
        cmd = f"ping -c 60 -W 1 {dut_ip}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = result.stdout
        match = re.search(r'(\d+)%\s+packet\s+loss', output)
        lost = int(int(match.group(1)) * 60 / 100) if match else None

    success = (lost == 0) if lost is not None else (result.returncode == 0)

    pytest.ping_result = "PASS" if success else "FAIL"
    if success:
        request.node._store["compat_compare"] = "PASS"
        logging.warning("✅ Ping 60/60 succeeded (0% loss)!")
    else:
        request.node._store["compat_compare"] = "FAIL"
        logging.error(f"❌ Ping failed: lost={lost}, output:\n{output[:300]}")

@pytest.mark.dependency(depends=["connect"])
@pytest.mark.wifi_connect
def test_multi_throughtput_tx(router_setting, request):
    if customer == "ONN" or project_name == "KitKat513" or project_id == "KitKat513":
        logging.info("⏩ Skipping TX throughput test for this project (ONN/KitKat513)")
        ping_status = getattr(pytest, 'ping_result', 'N/A')
        # 写入空结果，确保报告生成器能捕获
        tx_result = "SKIP"
        expect_data = "N/A"
        compare_pass = ping_status
        logging.info(f'tx_result {tx_result}')
        #pytest.skip("Skipped for ONN/KitKat513")

    else:
        tx_result = pytest.dut.get_tx_rate(router_setting, pytest.dut.rssi_num)
        logging.info(f'tx_result {tx_result}')
        expect_data = float(router_setting.expected_rate.split(' ')[0])
        logging.info(f'expect_data {expect_data}')
        # Record compare result for reporting, but do not fail the test.
        compare_pass = True
        try:
            values = [float(x) for x in str(tx_result).split(',') if str(x).strip()]
            compare_pass = all(v > float(expect_data) for v in values) if values else False
        except Exception:
            compare_pass = False

    #request.node._store['compat_compare'] = "PASS" if compare_pass else "FAIL"
    request.node._store['compat_compare'] = compare_pass if isinstance(compare_pass, str) else (
        "PASS" if compare_pass else "FAIL")
    request.node._store['return_value'] = (pytest.dut.channel, pytest.dut.rssi_num, expect_data, tx_result)
    logging.info(f'request.node._store {request.node._store['return_value']}')


@pytest.mark.dependency(depends=["connect"])
@pytest.mark.wifi_connect
def test_multi_throughtput_rx(router_setting, request):
    if customer == "ONN" or project_name == "KitKat513" or project_id == "KitKat513":
        logging.info("⏩ Skipping RX throughput test for this project (ONN/KitKat513)")
        ping_status = getattr(pytest, 'ping_result', 'N/A')
        # 写入空结果，确保报告生成器能捕获
        rx_result = "SKIP"
        expect_data = "N/A"
        compare_pass = ping_status #True
        #pytest.skip("Skipped for ONN/KitKat513")

    else:
        rx_result = pytest.dut.get_rx_rate(router_setting, pytest.dut.rssi_num)
        logging.info(f'rx_result {rx_result}')
        expect_data = float(router_setting.expected_rate.split(' ')[1])
        logging.info(f'expect_data {expect_data}')
        # Record compare result for reporting, but do not fail the test.
        compare_pass = True
        try:
            values = [float(x) for x in str(rx_result).split(',') if str(x).strip()]
            compare_pass = all(v > float(expect_data) for v in values) if values else False
        except Exception:
            compare_pass = False

    #request.node._store['compat_compare'] = "PASS" if compare_pass else "FAIL"
    request.node._store['compat_compare'] = compare_pass if isinstance(compare_pass, str) else (
        "PASS" if compare_pass else "FAIL")
    request.node._store['return_value'] = (pytest.dut.channel, pytest.dut.rssi_num, expect_data, rx_result)
    logging.info(f'request.node._store {request.node._store['return_value']}')

from src.test.compatibility.results import update_compat_test_result, write_realtime_compat_csv
@pytest.fixture(autouse=True)
def _realtime_compat_csv_update(request):
    # --- 提前缓存元数据 ---
    metadata = {}
    if "router_setting" in request.fixturenames and "power_setting" in request.fixturenames:
        try:
            router = request.getfixturevalue("router_setting")
            power = request.getfixturevalue("power_setting")
            metadata = {
                "pdu_ip": power.get("ip", "N/A"),
                "pdu_port": power.get("port", "N/A"),
                "band": getattr(router, "band", "N/A"),
                "ap_brand": f"{power.get('brand', '')} {power.get('model', '')}".strip() or "Unknown",
                "ssid": getattr(router, "ssid", "N/A"),
                "wifi_mode": getattr(router, "wireless_mode", "N/A"),
                "bandwidth": getattr(router, "bandwidth", "N/A"),
                "security": getattr(router, "security_mode", "open") or "open"
            }
        except Exception as e:
            logging.warning(f"[CSV METADATA] Failed: {e}")

    yield

    # --- 测试结束后更新状态 + 写 CSV ---
    store = getattr(request.node, "_store", {})
    compat_compare = store.get("compat_compare", "UNKNOWN")
    return_value = store.get("return_value", ("N/A", "N/A", "N/A", "N/A"))

    update_compat_test_result(
        nodeid=request.node.nodeid,
        test_name=request.node.name,
        compat_compare=compat_compare,
        return_value=return_value,
        metadata=metadata
    )

    report_dir = os.environ.get("PYTEST_REPORT_DIR")
    if report_dir:
        csv_path = Path(report_dir) / "compatibility_result.csv"
        write_realtime_compat_csv(str(csv_path))
