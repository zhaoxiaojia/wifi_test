# test_wifi_80211b_connectivity.py
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
    restore_ap_default_wireless
)

TCID = "WiFi-STA-FMD0001"


@allure.title("Wi-Fi 24G 802.11b Mode Connectivity Test")
@allure.description("""
1. Configure 2.4G Wi-Fi as 802.11b-only via Telnet
2. Enable Wi-Fi radio
3. Connect DUT to the 802.11b network
4. Play online video (verify internet)
""")
def test_wifi_24g_80211b_connectivity(wifi_adb_device):
    dut, serial, logdir, cfg = wifi_adb_device

    # === 从配置中提取路由器参数 ===
    wifi_config = cfg.get("router", {})
    ssid = wifi_config.get("24g_ssid")  # 使用 2.4G SSID 作为统一名称
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
        # === Step 1: 配置路由器为 802.11b-only (2.4G) ===
        with allure.step("Configure 2.4G Wi-Fi as 802.11b-only"):
            configure_ap_wireless_mode(router, band='2g', mode='b-only', ssid=ssid, password=password)

        # === Step 2: 验证是否为 b-only（关键步骤，失败则中止）===
        with allure.step("Verify AP is in expected 802.11b-only mode"):
            is_valid = verify_ap_wireless_mode(router, band='2g', expected_ssid=ssid, expected_mode='b-only')
            logging.info("AP is in expected 802.11b-only mode: %s", is_valid)

            if not is_valid:
                error_msg = (
                    f"AP did not enter 802.11b-only mode as expected.\n"
                    f"Router may not support this mode or configuration failed."
                )
                logging.error(error_msg)
                allure.attach(body=error_msg, name="AP Mode Verification Failed",
                              attachment_type=allure.attachment_type.TEXT)
                record_test_step(TCID, f"AP mode verification failed – aborting test", "FAIL", "FAILED")
                pytest.fail("AP mode verification failed – aborting test.")

        # === Step 3: DUT 连接 Wi-Fi ===
        with allure.step("Connect DUT to 802.11b network"):
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
            record_test_step(TCID, f"Connect to 802.11b {ssid}", "PASS" if connected else "FAIL", f"RSSI={rssi}")
            assert connected, f"Failed to connect to 802.11b SSID: {ssid}"

        # === Step 4: 播放在线视频（验证互联网）===
        with allure.step("Play online video to verify internet"):
            video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
            ping_ok = UiAutomationMixin._check_network_ping(serial)
            network_works = video_ok and ping_ok
            record_test_step(TCID, f"802.11b {ssid} network work well", "PASS" if network_works else "FAIL",
                             f"Network work well")

    finally:
        # === Step 5: 恢复 AP 默认设置 ===
        with allure.step("Restore AP to default"):
            restore_ap_default_wireless(
                router,
                band='2g',
                original_ssid=wifi_config.get("24g_ssid"),
                original_password=wifi_config.get("password")
            )
        router.quit()