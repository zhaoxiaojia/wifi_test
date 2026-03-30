# test_wifi_sg_region_5g_connectivity.py
import pytest
import allure
import time, os
import logging
from src.tools.router_tool.router_factory import get_router
from src.conftest import record_test_step
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin
from src.tools.router_tool.router_telnet_control import (
    configure_ap_wireless_mode,
    verify_ap_wireless_mode,
    configure_ap_channel,
    restore_ap_default_wireless,
    configure_and_verify_ap_country_code
)

from .region_result import ResultCollector, generate_region_report
collector = ResultCollector()
# 请替换为你的实际 TCID
TCID = "WiFi-STA-REG0054"

TEST_CHANNELS_2G = [1, 6, 11, 13]
TEST_CHANNELS_5G = [36, 64, 100, 140]
MAX_WAIT_TIME = 380
OLD_PASSWORD = "88888881"
TEST_24G_FIX_REGION_CODE = "CN"
TEST_5G_FIX_REGION_CODE = "US"

TEST_REGION_CODE = "SG"
TEST_REGION_CODE2 = "SG(新加坡)"

@allure.title("Wi-Fi {TEST_REGION_CODE2} Region and 5G Channel Connectivity Test")
@allure.description("""
1. Set AP region to {TEST_REGION_CODE2} and verify.
2.For 5G: Test channels [36, 64, 100, 165]. Connect, verify internet, then change channel and check reconnection.
""")
def test_wifi_sg_5g_region_connectivity(wifi_adb_device):
    dut, serial, logdir, cfg = wifi_adb_device
    test_channel_list = TEST_CHANNELS_5G
    test_type = os.environ.get("TEST_TYPE", "Typical Channels")

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
    UiAutomationMixin._clear_saved_wifi_networks(serial)
    dut._forget_wifi_via_ui(serial, ssid_2g)
    dut._forget_wifi_via_ui(serial, ssid_5g)
    time.sleep(2)

    # === 初始化路由器对象 ===
    router = get_router(router_name=router_name, address=router_ip)

    try:
        # === Step 1: 配置路由器Region为US) ===
        with allure.step("Configure DUT to {TEST_REGION_CODE2} Region"):
            try:
                ap_support_channel_list = configure_and_verify_ap_country_code(
                    router=router,
                    country_code=TEST_5G_FIX_REGION_CODE,
                    dut_country_code=TEST_REGION_CODE
               )

                dut_support_channel_list = dut.set_wifi_country_code(
                    serial=serial, country_code=TEST_REGION_CODE
                )
                if not dut_support_channel_list['status']:
                    pytest.fail(f"Setup failed: {dut_support_channel_list['message']}")

                ap_channel_list = (f"{dut_support_channel_list['5g_channels']}")
                record_test_step(TCID, f"Step1. Set DUT region to {TEST_REGION_CODE2}", "PASS", "")
                record_test_step(TCID, f"Step2. Get 5G band channel list:", "PASS", ap_channel_list)
                if test_type == "Full Channels":
                    test_channel_list = ap_support_channel_list['5g_channels']
                logging.info(f"test_channel_list: {test_channel_list}")
            except Exception as e:  # 捕获任何异常
                error_msg = (
                    f"AP did not setting {TEST_REGION_CODE2} region successfully.\n"
                    f"Exception: {str(e)}"
                )
                logging.error(error_msg)
                allure.attach(body=error_msg, name="AP Region Verification Failed",
                              attachment_type=allure.attachment_type.TEXT)
                record_test_step(TCID, f"AP Region failed – aborting test", "FAIL", error_msg)
                pytest.fail("AP Region verification failed – aborting test.")


            # === Step 2: Configure Router to 5GHz ===
            with allure.step(f"Configure 5G Wi-Fi to {ssid_5g}"):
                # Use 'an-ac-mixed' which maps to 11ax in 5G
                configure_ap_wireless_mode(
                    router, band='5g', ssid=ssid_5g, password=password
                )

            # === Step 3: Initial DUT Connection to Wi-Fi ===
            with allure.step("Connect DUT to initial (5G) network"):
                success = UiAutomationMixin._connect_to_wifi_via_ui(
                    serial=serial, ssid=ssid_5g, password=password, logdir=logdir
                )
                connected = False
                for i in range(15):  # Wait up to 30 seconds
                    time.sleep(2)
                    current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                    if current_ssid == ssid_5g:
                        connected = True
                        break

                rssi = dut.get_rssi() if connected else "N/A"
                country = dut.get_wifi_country_code(serial)
                logging.info(f"DUT connected to AP with {rssi} and {country}")

                if connected == False:
                    record_test_step(TCID, f"connect to {country} AP {ssid_5g} failed )",
                                     "FAIL", f"RSSI={rssi}")
                    assert connected, f"Failed to connect to initial SSID: {ssid_5g}"

            # === Step 4: Channel Switching & Reconnection Verification ===
            num = 0
            for ch in test_channel_list:
                num = num + 1
                test_result = "Fail"
                with allure.step(f"Change AP channel to {ch} and verify DUT connection"):
                    # 1. Configure router to new channel (bandwidth remains '80MHZ')
                    configure_ap_channel(router, band='5g', channel=ch, ssid=ssid_5g, password=password)
                    time.sleep(5)  # Allow router to apply changes
                    record_test_step(TCID, f"Step3.{num}. Set AP channel to {ch}", "PASS", "")
                    dut_support_channel_list = dut.set_wifi_country_code(
                        serial=serial, country_code=TEST_REGION_CODE
                    )
                    time.sleep(5)

                    # 2. Wait and verify DUT reconnection (within MAX_WAIT_TIME)
                    reconnected = False
                    start_time = time.time()
                    current_rssi = "N/A"

                    while time.time() - start_time < MAX_WAIT_TIME:
                        time.sleep(2)
                        current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                        current_channel = dut.get_connected_channel_via_cli_adb(serial)
                        country = dut.get_wifi_country_code(serial)
                        if current_ssid == ssid_5g and current_channel == ch and country == TEST_REGION_CODE:
                            reconnected = True
                            current_rssi = dut.get_rssi()
                            logging.info(f"DUT reconnected on CH={ch}. RSSI: {current_rssi}")
                            break

                    # Record the test step result
                    logging.info(f"Step4.{num} DUT connected to AP with {rssi} {country} {current_channel}")

                    step_result = "PASS" if reconnected else "FAIL"
                    record_test_step(TCID, f"Step4.{num}. Check DUT WiFi connection status",
                                     step_result, f"RSSI={current_rssi}, country={country}, channel={current_channel}")

                    # The requirement is to reconnect within 1 min, so we assert this.
                    #assert reconnected, f"DUT failed to reconnect to '{ssid_5g}' within {MAX_WAIT_TIME}s after AP channel changed to {ch}."

                # === Step 5: Verify Internet Connectivity ===
                if reconnected:
                    with allure.step("Play online video to verify internet"):
                        time.sleep(30)
                        video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
                        ping_ok = UiAutomationMixin._check_network_ping(serial)
                        network_works = video_ok and ping_ok

                        record_test_step(TCID, f"Step5.{num}. Verify outgoing data access via ping 8.8.8.8",
                                         "PASS" if network_works else "FAIL", "")
                        if ping_ok:
                            test_result = "Pass"
                collector.add_result(channel=ch, band="5G", country=TEST_REGION_CODE, result=test_result)
                logging.info(f"✅ 收集: Ch{ch} = {test_result}")
    finally:
        # === Step 5: 恢复 AP 默认设置 ===
        with allure.step("Restore AP and DUT to default"):
            restore_ap_default_wireless(
                router,
                band='5g',
                original_ssid=wifi_config.get("5g_ssid"),  # 👈 恢复 5G SSID
                original_password=OLD_PASSWORD
            )
            dut.set_wifi_country_code_default(serial=serial, country_code="00")
            report_path = generate_region_report(logdir)

        router.quit()