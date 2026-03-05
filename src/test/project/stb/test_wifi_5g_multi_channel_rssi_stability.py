# test_wifi_5g_multi_channel_rssi_stability.py
import pytest
import allure
import time
import logging
from src.tools.router_tool.router_factory import get_router
from src.conftest import record_test_step
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin
from src.tools.router_tool.router_telnet_control import (
    configure_ap_channel,
    verify_ap_channel_and_beacon,
    restore_ap_default_wireless
)

TCID = "WiFi-STA-FCH0056"  #

@allure.title("Wi-Fi 5GHz Multi-Channel RSSI Stability Test (CH36 → CH64/100/149/161)")
@allure.description("""
1. DUT connects to a fixed 5GHz AP initially on Channel 36.
2. The AP's channel is switched sequentially to 64, 100, 149, and 161.
3. After each switch, verify DUT automatically reconnects and measure RSSI via 'iw wlan1 link'.
4. Ensure RSSI remains stable across all tested channels.
""")
def test_wifi_5g_multi_channel_rssi_stability(wifi_adb_device):
    dut, serial, logdir, cfg = wifi_adb_device

    # === 从配置中提取路由器参数 ===
    wifi_config = cfg.get("router", {})
    ssid = wifi_config.get("5g_ssid")
    password = wifi_config.get("password", "88888888")
    router_ip = wifi_config.get("address")
    router_name = wifi_config.get("name")

    if not all([router_ip, router_name]):
        raise ValueError(f"Missing router config: ip={router_ip}, name={router_name}")

    # --- Step 0: 清理 DUT 已保存网络 ---
    UiAutomationMixin._clear_saved_wifi_networks(serial)
    dut._forget_wifi_via_ui(serial, ssid)
    time.sleep(2)

    # 定义要测试的信道列表
    target_channels = [64, 100, 149, 161]
    rssi_values = {}  # 用于记录每个信道的RSSI
    failed_channels = {}

    # === 初始化路由器对象 ===
    router = get_router(router_name=router_name, address=router_ip)

    try:
        # === Step 1: 初始连接 - 配置并连接到信道 36 ===
        with allure.step("Initial Setup: Connect DUT to 5GHz network on channel 36"):
            # 配置路由器为信道36
            configure_ap_channel(router, band='5g', channel=36, ssid=ssid, password=password)
            is_valid = verify_ap_channel_and_beacon(router, band='5g', expected_channel=36, expected_ssid=ssid)
            #assert is_valid, "Failed to configure AP on initial channel 36."

            # DUT 连接 Wi-Fi
            success = UiAutomationMixin._connect_to_wifi_via_ui(
                serial=serial, ssid=ssid, password=password, logdir=logdir
            )
            connected = False
            for i in range(15):
                time.sleep(2)
                current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                if current_ssid == ssid:
                    connected = True
                    break

            #assert connected, f"Failed to connect to initial 5GHz SSID: {ssid} on channel 36"
            initial_rssi = dut.get_rssi()
            record_test_step(TCID, f"Connect to CH36", "PASS" if connected else "FAIL", f"RSSI={initial_rssi}")
            logging.info(f"Initial connection RSSI on CH36: {initial_rssi}")
            rssi_values[36] = initial_rssi
            lower_bound = initial_rssi - 10  # e.g., -30 -10 = -40
            upper_bound = initial_rssi + 10  # e.g., -30 +10 = -20

        # === Step 2: 信道漫游稳定性测试 ===
        for ch in target_channels:
            with allure.step(f"Change AP to Channel {ch} and verify DUT reconnection"):
                # 1. 配置路由器到新信道
                configure_ap_channel(router, band='5g', channel=ch, ssid=ssid, password=password)
                is_valid = verify_ap_channel_and_beacon(router, band='5g', expected_channel=ch, expected_ssid=ssid)
                #assert is_valid, f"Failed to configure AP on channel {ch}."

                # 2. 等待并验证DUT重连
                reconnected = False
                max_wait_time = 300  # 给予DUT最多30秒重连
                start_time = time.time()
                current_rssi = "N/A"

                while time.time() - start_time < max_wait_time:
                    time.sleep(2)
                    current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                    if current_ssid == ssid:
                        reconnected = True
                        current_rssi = dut.get_rssi()
                        rssi_values[ch] = current_rssi
                        logging.info(f"DUT reconnected on CH{ch}. RSSI: {current_rssi}")
                        break

                # 记录测试步骤结果
                step_result = "PASS" if reconnected else "FAIL"
                record_test_step(TCID, f"Roam to CH{ch} and reconnect", step_result, f"RSSI={current_rssi}")
                #assert reconnected, f"DUT failed to reconnect to SSID '{ssid}' after AP switched to channel {ch}."

                # === Step 3: 验证 - 信道的RSSI应在初始RSSI ±10 dB范围内 ===
                with allure.step("Final Verification: Each channel's RSSI within ±10 dB of initial (CH36)"):
                    rssi = rssi_values.get(ch, "N/A")
                    if rssi == "N/A" or not isinstance(rssi, (int, float)):
                        stable = False
                        failed_channels.append(f"CH{ch}: Invalid RSSI ({rssi})")
                    elif not (lower_bound <= rssi <= upper_bound):
                        stable = False
                        failed_channels.append(f"CH{ch}: {rssi} (expected [{lower_bound}, {upper_bound}])")
                    else:
                        stable = True

                    final_msg = (
                        f"Initial RSSI (CH36): {initial_rssi} dB. "
                        f"Acceptable range: [{lower_bound}, {upper_bound}] dB. "
                        f"Results: {rssi_values}"
                    )
                    if failed_channels:
                        final_msg += f" | Failed: {', '.join(failed_channels)}"

                    record_test_step(TCID, f"CH{ch} Check Result:", "PASS" if stable else "FAIL",
                                     final_msg)
                    #assert stable, f"Some channels' RSSI out of ±10 dB range from initial value ({initial_rssi} dB)."

    finally:
        # === Step 4: 恢复 AP 默认设置 ===
        with allure.step("Restore AP to default"):
            restore_ap_default_wireless(
                router, band='5g',
                original_ssid=wifi_config.get("5g_ssid"),
                original_password=wifi_config.get("password")
            )
            record_test_step(TCID, "Restore AP to default", "PASS", "Environment cleaned up")
            router.quit()