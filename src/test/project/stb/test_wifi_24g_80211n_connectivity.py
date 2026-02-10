# test_wifi_80211n_connectivity.py
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

TCID = "WiFi-STA-FMD0003"  # 新 TCID

@allure.title("Wi-Fi 802.11n Mode Connectivity Test (2.4GHz)")
@allure.description("""
1. Configure 2.4G Wi-Fi as 802.11n-only via Telnet
2. Enable Wi-Fi radio
3. Connect DUT to the 802.11n network
4. Play online video to verify internet connectivity
""")
def test_wifi_24g_80211n_connectivity(wifi_adb_device):
    dut, serial, logdir, cfg = wifi_adb_device

    # === 提取路由器配置 ===
    wifi_config = cfg.get("router", {})
    ssid = wifi_config.get("24g_ssid")
    password = wifi_config.get("password", "88888888")
    router_ip = wifi_config.get("address")
    router_name = wifi_config.get("name")
    router = get_router(router_name=router_name, address=router_ip)

    if not all([router_ip, router_name, ssid]):
        raise ValueError(f"Missing router config: ip={router_ip}, name={router_name}, ssid={ssid}")

    # --- Step 0: 清理 DUT 已保存网络 ---
    UiAutomationMixin._clear_saved_wifi_networks(serial)
    dut._forget_wifi_via_ui(serial, ssid)
    time.sleep(2)

    try:
        # === Step 1: 配置路由器为 802.11n-only (2.4G) ===
        with allure.step("Configure 2.4G Wi-Fi as 802.11n-only"):
            configure_ap_wireless_mode(router, band='2g', mode='n-only', ssid=ssid, password=password)

        # === Step 2: 验证是否为 n-only（关键步骤，失败则中止）===
        with allure.step("Verify AP is in expected 802.11n-only mode"):
            is_valid = verify_ap_wireless_mode(router, band='2g', expected_ssid=ssid, expected_mode='n-only')
            logging.info("AP is in expected 802.11n-only mode: %s", is_valid)

            if not is_valid:
                error_msg = (
                    f"AP did not enter 802.11n-only mode as expected.\n"
                    f"Router may not support this mode or configuration failed."
                )
                logging.error(error_msg)
                allure.attach(body=error_msg, name="AP Mode Verification Failed",
                              attachment_type=allure.attachment_type.TEXT)
                record_test_step(TCID, f"AP mode verification failed – aborting test", "FAIL", "FAILED")
                pytest.fail("AP mode verification failed – aborting test.")

        # === Step 3: DUT 连接 Wi-Fi ===
        with allure.step("Connect DUT to 802.11n network"):
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
            record_test_step(TCID, f"Connect to 802.11n {ssid}", "PASS" if connected else "FAIL", f"RSSI={rssi}")
            assert connected, f"Failed to connect to 802.11n SSID: {ssid}"

        # === Step 4: 播放在线视频（验证互联网）===
        with allure.step("Play online video to verify internet"):
            video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
            ping_ok = UiAutomationMixin._check_network_ping(serial)
            network_works = video_ok and ping_ok
            record_test_step(TCID, f"802.11n {ssid} network works", "PASS" if network_works else "FAIL", "Internet OK")

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