# test_wifi_cn_region_24g_connectivity.py
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
    restore_ap_default_wireless,
    configure_and_verify_ap_country_code,
)

# 请替换为你的实际 TCID
TCID = "WiFi-STA-REG0003"

TEST_CHANNELS_2G = [1, 6, 11]
TEST_CHANNELS_5G = [36, 100, 165]
MAX_WAIT_TIME = 180

@allure.title("Wi-Fi China Region and 2.4G Channel Connectivity Test")
@allure.description("""
1. Set AP region to China and verify.
2.For 2.4G: Test channels [1, 6, 11]. Connect, verify internet, then change channel and check reconnection.
""")
def test_wifi_cn_region_24g_connectivity(wifi_adb_device):
    dut, serial, logdir, cfg = wifi_adb_device

    # === 从配置中提取路由器参数 ===
    wifi_config = cfg.get("router", {})
    ssid_5g = wifi_config.get("5g_ssid")
    ssid_2g = wifi_config.get("24g_ssid")
    password = wifi_config.get("password", "88888888")
    security = wifi_config.get("security_mode", "WPA2-Personal")
    router_ip = wifi_config.get("address")
    router_name = wifi_config.get("name")

    if not all([router_ip, router_name]):
        raise ValueError(f"Missing router config: ip={router_ip}, name={router_name}")

    # # --- Step 0: 清理 DUT 已保存网络 ---
    # UiAutomationMixin._clear_saved_wifi_networks(serial)
    # dut._forget_wifi_via_ui(serial, ssid_2g)
    # dut._forget_wifi_via_ui(serial, ssid_5g)
    # time.sleep(2)

    # === 初始化路由器对象 ===
    router = get_router(router_name=router_name, address=router_ip)
    try:
        # === Step 1: 配置路由器Region为CN) ===
        with allure.step("Configure AP to China Region"):
            try:
                support_channel_list = configure_and_verify_ap_country_code(
                    router=router,
                    country_code="CN"
                )
                ap_channel_list = (f"✅ Country code verified as China. "
                                   f"2.4G Channels: {support_channel_list['2g_channels']}, ")
                record_test_step(TCID, f"AP China Region ", "PASS", ap_channel_list)
            except Exception as e:  # 捕获任何异常
                error_msg = (
                    f"AP did not setting China region successfully.\n"
                    f"Exception: {str(e)}"
                )
                logging.error(error_msg)
                allure.attach(body=error_msg, name="AP Region Verification Failed",
                              attachment_type=allure.attachment_type.TEXT)
                record_test_step(TCID, f"AP Region failed – aborting test", "FAIL", error_msg)
                pytest.fail("AP Region verification failed – aborting test.")

            time.sleep(100)
            # === Step 2: Configure Router to 2.4GHz auto mode with auto bandwidth ===
            with allure.step("Configure 2.4G Wi-Fi as auto with auto bandwidth"):
                # Use 'an-ac-mixed' which maps to 11ax in 5G
                configure_ap_wireless_mode(
                    router, band='2g', ssid=ssid_2g, password=password
                )

            # === Step 3: Initial DUT Connection to Wi-Fi ===
            with allure.step("Connect DUT to initial auto (2.4G) network"):
                success = UiAutomationMixin._connect_to_wifi_via_ui(
                    serial=serial, ssid=ssid_2g, password=password, logdir=logdir
                )
                connected = False
                for i in range(15):  # Wait up to 30 seconds
                    time.sleep(2)
                    current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                    if current_ssid == ssid_2g:
                        connected = True
                        break

                rssi = dut.get_rssi() if connected else "N/A"
                record_test_step(TCID, f"Initial connect to {ssid_2g} (CH Auto))",
                                 "PASS" if connected else "FAIL", f"RSSI={rssi}")
                assert connected, f"Failed to connect to initial SSID: {ssid_2g}"

            # === Step 4: Channel Switching & Reconnection Verification ===
            for ch in TEST_CHANNELS_2G:
                with allure.step(f"Change AP channel to {ch} and verify DUT reconnection"):
                    # 1. Configure router to new channel (bandwidth remains '80MHZ')
                    configure_ap_channel(router, band='2g', channel=ch, ssid=ssid_2g, password=password)
                    time.sleep(5)  # Allow router to apply changes

                    # 2. Wait and verify DUT reconnection (within MAX_WAIT_TIME)
                    reconnected = False
                    start_time = time.time()
                    current_rssi = "N/A"

                    while time.time() - start_time < MAX_WAIT_TIME:
                        time.sleep(2)
                        current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                        if current_ssid == ssid_2g:
                            reconnected = True
                            current_rssi = dut.get_rssi()
                            logging.info(f"DUT reconnected on CH={ch}. RSSI: {current_rssi}")
                            break

                    # Record the test step result
                    step_result = "PASS" if reconnected else "FAIL"
                    record_test_step(TCID, f"Switch to CH={ch} and reconnect",
                                     step_result, f"RSSI={current_rssi}")

                    # The requirement is to reconnect within 1 min, so we assert this.
                    assert reconnected, f"DUT failed to reconnect to '{ssid_2g}' within {MAX_WAIT_TIME}s after AP channel changed to {ch}."

                # === Step 5: Verify Internet Connectivity ===
                with allure.step("Play online video to verify internet"):
                    time.sleep(150)
                    video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
                    ping_ok = UiAutomationMixin._check_network_ping(serial)
                    network_works = video_ok and ping_ok
                    record_test_step(TCID, f"Auto (2.4G) {ssid_2g} network works well",
                                     "PASS" if network_works else "FAIL", "Network work well")

    finally:
        # === Step 5: 恢复 AP 默认设置 ===
        with allure.step("Restore AP to default"):
            restore_ap_default_wireless(
                router,
                band='2g',
                original_ssid=wifi_config.get("2g_ssid"),  # 👈 恢复 5G SSID
                original_password=wifi_config.get("password")
            )
        router.quit()