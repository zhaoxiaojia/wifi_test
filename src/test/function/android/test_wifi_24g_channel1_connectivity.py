# test_wifi_2g_channel1_connectivity.py
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

TCID = "WiFi-STA-FCH0001"


@allure.title("Wi-Fi 2.4GHz Channel 1 Connectivity Test")
@allure.description("""
1. Configure 2.4G Wi-Fi on channel 1 via Telnet
2. Enable Wi-Fi radio
3. Connect DUT to the 2.4GHz network on channel 1
4. Play online video to verify internet connectivity
""")
def test_wifi_2g_channel1_connectivity(wifi_adb_device):
    dut, serial, logdir, cfg = wifi_adb_device

    # === 从配置中提取路由器参数 ===
    wifi_config = cfg.get("router", {})
    #logging.info(f"wifi_config: {wifi_config}")
    ssid = wifi_config.get("24g_ssid")  # 使用 2G SSID
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
        # === Step 1: 配置路由器为 2.4GHz 默认模式，信道1 ===
        with allure.step("Configure 2.4G Wi-Fi on channel 1"):
            # 调用驱动函数，指定 band='2g' 和 mode='auto'（默认模式）
            # 注意：configure_ap_wireless_mode 函数需要扩展以支持信道设置
            configure_ap_channel(router, band='2g', channel=1, ssid=ssid, password=password)

        # === Step 2: 验证是否配置成功（关键步骤，失败则中止）===
        with allure.step("Verify AP is configured on channel 1"):
            is_valid = verify_ap_channel_and_beacon(router, band='2g', expected_channel=1, expected_ssid=ssid)
            logging.info("AP is configured on channel 1: %s", is_valid)
            if not is_valid:
                error_msg = (
                    f"AP did not configure properly on channel 1.\n"
                    f"Router may not support this configuration or setup failed."
                )
                logging.error(error_msg)
                allure.attach(body=error_msg, name="AP Channel 1 Configuration Failed",
                              attachment_type=allure.attachment_type.TEXT)
            record_test_step(TCID, f"Configurate AP Channel 1",  "PASS" if is_valid else "FAIL",
                                 "AP Channel 1 Setting")
            if not is_valid:
                pytest.fail("AP channel 1 configuration verification failed – aborting test.")

        # === Step 3: DUT 连接 Wi-Fi ===
        with allure.step("Connect DUT to 2.4GHz network on channel 1"):
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
            record_test_step(TCID, f"Connect to 2.4GHz {ssid} on channel 1", "PASS" if connected else "FAIL",
                             f"RSSI={rssi}")
            assert connected, f"Failed to connect to 2.4GHz SSID: {ssid}"

        # === Step 4: 播放在线视频（验证互联网）===
        with allure.step("Play online video to verify internet"):
            video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
            ping_ok = UiAutomationMixin._check_network_ping(serial)
            network_works = video_ok and ping_ok
            record_test_step(TCID, f"2.4GHz {ssid} network work well on channel 1", "PASS" if network_works else "FAIL",
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