# test_wifi_ssid_format_compatibility.py
import pytest
import allure
import time
import logging
from src.tools.router_tool.router_factory import get_router
from src.conftest import record_test_step
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin
from src.tools.router_tool.router_telnet_control import (
    configure_ap_channel,
    restore_ap_default_wireless
)

TCID = "WiFi-STA-FSSID0001"

# SSID 测试用例定义
SSID_TEST_CASES = [
    {
        "name": "Mixed_Chars",
        "ssid": "中国123@FAE-sqa",
        "desc": "Mixed Chars includes Chinese"
    },
    {
        "name": "Specific Chars",
        "ssid": "Test～!@#12345678", #"Test～!@# $ %^&*()_+-= 12345678",
        "desc": "Specific Chars"
    },
    {
        "name": "Max_Length",
        "ssid": "0123456789" * 3 + "01",  # 32 字符（Wi-Fi SSID 最大长度）
        "desc": "32 Bytes SSID"
    }
]


@allure.title("Wi-Fi SSID Format Compatibility Test")
@allure.description("""
1. Configure AP with special SSID (mixed/UTF-8/space/max-length)
2. Connect DUT via UI
3. Play online video
4. Toggle Wi-Fi → auto reconnect
5. Reboot DUT → auto reconnect
6. Reboot router → auto reconnect
""")
@pytest.mark.parametrize("ssid_case", SSID_TEST_CASES, ids=[c["name"] for c in SSID_TEST_CASES])
def test_wifi_ssid_format_compatibility(wifi_adb_device, ssid_case):
    dut, serial, logdir, cfg = wifi_adb_device

    # === 提取路由器配置 ===
    wifi_config = cfg.get("router", {})
    password = wifi_config.get("password", "88888888")
    security = wifi_config.get("security_mode", "WPA2-Personal")
    router_ip = wifi_config.get("address")
    router_name = wifi_config.get("name")

    if not all([router_ip, router_name]):
        raise ValueError(f"Missing router config: ip={router_ip}, name={router_name}")

    target_ssid = ssid_case["ssid"]
    test_name = ssid_case["name"]
    desc = ssid_case["desc"]

    router = None
    try:
        # === Step 1: 配置路由器 SSID (仅 5G，2.4G 可选) ===
        with allure.step(f"Configure 5G AP with SSID: '{target_ssid}' ({desc})"):
            router = get_router(router_name=router_name, address=router_ip)
            # 清理旧网络
            dut._forget_wifi_via_ui(serial)

            # Setting 5G SSID
            configure_ap_channel(router, band='5g', channel=36, ssid=target_ssid, password=password)

        # === Step 2: DUT 连接 ===
        with allure.step(f"Connect to SSID: '{target_ssid}'"):
            success = UiAutomationMixin._connect_to_wifi_via_ui(
                serial=serial,
                ssid=target_ssid,
                password=password,
                logdir=logdir
            )
            time.sleep(20)
            current_ssid = dut.get_connected_ssid_via_cli_adb(serial)
            connected = bool(current_ssid and "Not connected" not in current_ssid)
            rssi = dut.get_rssi() if connected else "N/A"
            record_test_step(TCID, f"Connect to SSID {target_ssid}", "PASS" if connected else "FAIL", f"RSSI={rssi}")
            assert connected, f"Failed to connect to SSID: {target_ssid}"

        # === Step 3: 播放在线视频 ===
        with allure.step("Play online video (YouTube)"):
            video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
            record_test_step(TCID, f"Video Playback Well in {target_ssid}", "PASS" if video_ok else "FAIL", "")
            assert video_ok, "Video playback failed!"

        # === Step 4: Toggle Wi-Fi ===
        with allure.step("Toggle Wi-Fi OFF/ON"):
            UiAutomationMixin._disable_wifi_adb(serial)
            time.sleep(3)
            UiAutomationMixin._enable_wifi_adb(serial)
            time.sleep(20)
            current_ssid = dut.get_connected_ssid_via_cli_adb(serial)
            reconnected = bool(current_ssid and "Not connected" not in current_ssid)
            record_test_step(TCID, f"After Wi-Fi Switch Re-connected {target_ssid}", "PASS" if reconnected else "FAIL", "Auto-reconnect")
            assert reconnected, "Failed to reconnect after Wi-Fi toggle"

        # === Step 5: 重启 DUT ===
        with allure.step("Reboot DUT"):
            booted, _ = dut.wait_for_device_boot(serial, timeout=150)
            assert booted, "DUT failed to boot"
            time.sleep(15)
            current_ssid = dut.get_connected_ssid_via_cli_adb(serial)
            reconnected = bool(current_ssid and "Not connected" not in current_ssid)
            #record_test_step(TCID, f"DUT Reboot {test_name}", "PASS" if reconnected else "FAIL", "Auto-reconnect")
            assert reconnected, "Failed to reconnect after DUT reboot"

        # === Step 6: 重启路由器 ===
        with allure.step("Reboot router"):
            router.telnet_write("reboot", wait_prompt=False)
            time.sleep(200)  # 路由器启动 + DUT 重连
            current_ssid = dut.get_connected_ssid_via_cli_adb(serial)
            reconnected = bool(current_ssid and "Not connected" not in current_ssid)
            record_test_step(TCID, f"After Router Reboot Re-connected {target_ssid}", "PASS" if reconnected else "FAIL", "Auto-reconnect")
            assert reconnected, "Failed to reconnect after router reboot"

    finally:
        # === 清理：恢复默认 SSID（从配置中读取）===
        try:
            restore_ap_default_wireless(
                router, band='5g',
                original_ssid=wifi_config.get("5g_ssid"),
                original_password=wifi_config.get("password")
            )
            record_test_step(TCID, "Restore AP to default", "PASS", "Environment cleaned up")
            logging.info(f"✅ Restored default 5G SSID: {target_ssid}")
        except Exception as e:
            logging.error(f"⚠️ Failed to restore default SSID: {e}")
        finally:
            if router:
                router.quit()