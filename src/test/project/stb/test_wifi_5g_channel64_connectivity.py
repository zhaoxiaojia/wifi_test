# test_wifi_5g_channel64_connectivity.py
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

TCID = "WiFi-STA-FCH0010"

@allure.title("Wi-Fi 5GHz Channel 64 Connectivity Test")
@allure.description("""
1. Configure 5G Wi-Fi on channel 64 via Telnet
2. Enable Wi-Fi radio
3. Connect DUT to the 5GHz network on channel 64
4. Play online video to verify internet connectivity
""")
def test_wifi_5g_channel64_connectivity(wifi_adb_device):
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
        # === Step 1: 配置路由器为 5GHz 默认模式，信道64 ===
        with allure.step("Configure 5G Wi-Fi on channel 64"):
            # 调用驱动函数，指定 band='5g' 和 channel=64
            configure_ap_channel(router, band='5g', channel=64, ssid=ssid, password=password)

        # === Step 2: 验证是否配置成功（关键步骤，失败则中止）===
        with allure.step("Verify AP is configured on channel 64"):
            is_valid = verify_ap_channel_and_beacon(router, band='5g', expected_channel=64, expected_ssid=ssid)
            logging.info("AP is configured on channel 64: %s", is_valid)
            if not is_valid:
                error_msg = (
                    f"AP did not configure properly on channel 64.\n"
                    f"Router may not support this configuration or setup failed."
                )
                logging.error(error_msg)
                allure.attach(body=error_msg, name="AP Channel 64 Configuration Failed", attachment_type=allure.attachment_type.TEXT)
                record_test_step(TCID, f"Configurate AP Channel 64", "PASS" if is_valid else "FAIL", "AP Channel 64 Setting")
                pytest.fail("AP channel 64 configuration verification failed – aborting test.")

        # === Step 3: DUT 连接 Wi-Fi ===
        with allure.step("Connect DUT to 5GHz network on channel 64"):
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
            record_test_step(TCID, f"Connect to 5GHz {ssid} on channel 64", "PASS" if connected else "FAIL", f"RSSI={rssi}")
            assert connected, f"Failed to connect to 5GHz SSID: {ssid}"

        # === Step 4: 播放在线视频（验证互联网）===
        with allure.step("Play online video to verify internet"):
            video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
            ping_ok = UiAutomationMixin._check_network_ping(serial)
            network_works = video_ok and ping_ok
            record_test_step(TCID, f"5GHz {ssid} network work well on channel 64", "PASS" if network_works else "FAIL", f"Network work well")

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