# test_wifi_5g_80211n_channel165_connectivity.py
import pytest
import allure
import time
import logging
from src.tools.router_tool.router_factory import get_router
from src.conftest import record_test_step
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin
from src.tools.router_tool.router_telnet_control import (
    configure_ap_wireless_mode,
    verify_ap_wireless_mode,
    configure_ap_channel,
    configure_ap_bandwidth,
    verify_ap_channel_and_beacon,
    restore_ap_default_wireless
)

TCID = "WiFi-STA-FCH0028"  # 请根据您的实际用例编号规则调整


@allure.title("Wi-Fi 5GHz Channel 165 with 802.11n and HT20  Mode Connectivity Test")
@allure.description("""
1. Configure 5G Wi-Fi on channel 165 with 802.11n-only mode via Telnet
2. Enable Wi-Fi radio
3. Connect DUT to the 5GHz network on channel 165
4. Play online video to verify internet connectivity
""")
def test_wifi_5g_channel165_80211n_ht20_connectivity(wifi_adb_device):
    dut, serial, logdir, cfg = wifi_adb_device

    # === 从配置中提取路由器参数 ===
    wifi_config = cfg.get("router", {})
    ssid = wifi_config.get("5g_ssid")  # 使用 5G SSID
    password = wifi_config.get("password", "88888888")
    security = wifi_config.get("security_mode", "WPA2-Personal")
    router_ip = wifi_config.get("address")
    router_name = wifi_config.get("name")

    if not all([router_ip, router_name]):
        raise ValueError(f"Missing router config: ip={router_ip}, name={router_name}")

    # --- Step 0: 清理 DUT 已保存网络 ---
    UiAutomationMixin._clear_saved_wifi_networks(serial)
    dut._forget_wifi_via_ui(serial, ssid)
    time.sleep(2)

    # === 初始化路由器对象 ===
    router = get_router(router_name=router_name, address=router_ip)

    try:
        # === Step 1: 配置路由器为 5GHz 802.11n-only 模式，并设置信道为 165 ===
        with allure.step("Configure 5G Wi-Fi as 802.11n-only on channel 165"):
            # 1. 再设置无线模式为 'an-only' (802.11n)
            configure_ap_wireless_mode(router, band='5g', mode='an-only', ssid=ssid, password=password)
            router.set_5g_channel_bandwidth(channel=165, bandwidth='20MHZ')
            router.commit()



        # === Step 2: 验证是否为 an-only 并且在信道 165（关键步骤，失败则中止）===
        with allure.step("Verify AP is in expected 802.11n-only mode on channel 165"):
            # 首先验证无线模式
            is_mode_valid = verify_ap_wireless_mode(router, band='5g', expected_ssid=ssid, expected_mode='an-only')
            # 然后验证信道
            is_channel_valid = verify_ap_channel_and_beacon(router, band='5g', expected_channel=165, expected_ssid=ssid)

            is_valid = is_mode_valid and is_channel_valid
            logging.info("AP is in expected 802.11n-only mode on channel 165: %s", is_valid)

            if not is_valid:
                error_msg = (
                    f"AP did not enter 802.11n-only mode or is not on channel 165 as expected.\n"
                    f"Mode valid: {is_mode_valid}, Channel valid: {is_channel_valid}"
                )
                logging.error(error_msg)
                allure.attach(body=error_msg, name="AP Configuration Verification Failed",
                              attachment_type=allure.attachment_type.TEXT)
                record_test_step(TCID, f"AP config verification failed – aborting test", "FAIL", "FAILED")
                pytest.fail("AP configuration verification failed – aborting test.")

        # === Step 3: DUT 连接 Wi-Fi ===
        with allure.step("Connect DUT to 802.11n (5G) network on channel 165"):
            success = UiAutomationMixin._connect_to_wifi_via_ui(
                serial=serial,
                ssid=ssid,
                password=password,
                logdir=logdir
            )
            connected = False
            for i in range(15):
                time.sleep(2)
                current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                if current_ssid == ssid:
                    connected = True
                    break

            rssi = dut.get_rssi() if connected else "N/A"
            record_test_step(TCID, f"Connect to 802.11n (5G) {ssid} on CH165", "PASS" if connected else "FAIL",
                             f"RSSI={rssi}")
            assert connected, f"Failed to connect to 802.11n (5G) SSID: {ssid}"

        # === Step 4: 播放在线视频（验证互联网）===
        with allure.step("Play online video to verify internet"):
            video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
            ping_ok = UiAutomationMixin._check_network_ping(serial)
            network_works = video_ok and ping_ok
            record_test_step(TCID, f"802.11n (5G) {ssid} on CH165 network work well",
                             "PASS" if network_works else "FAIL", f"Network work well")

    finally:
        # === Step 5: 恢复 AP 默认设置 ===
        with allure.step("Restore AP to default"):
            restore_ap_default_wireless(
                router, band='5g',
                original_ssid=wifi_config.get("5g_ssid"),
                original_password=wifi_config.get("password")
            )
            record_test_step(TCID, "Restore AP to default", "PASS", "Environment cleaned up")
            router.quit()