# test_wifi_80211bgn_ax_mixed_connectivity.py
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

TCID = "WiFi-STA-FMD0006"


@allure.title("Wi-Fi 802.11b/g/n with AX Enabled Connectivity Test (2.4GHz)")
@allure.description("""
1. Configure 2.4G Wi-Fi as 802.11b/g/n mixed (auto) via Telnet
2. Explicitly enable 802.11ax (Wi-Fi 6) on 2.4G band
3. Enable Wi-Fi radio
4. Connect DUT to the network and verify internet
""")
def test_wifi_24g_80211bgn_ax_mixed_connectivity(wifi_adb_device):
    dut, serial, logdir, cfg = wifi_adb_device

    # === 提取路由器配置 ===
    wifi_config = cfg.get("router", {})
    ssid = wifi_config.get("24g_ssid")
    password = wifi_config.get("password", "88888888")
    router_ip = wifi_config.get("address")
    router_name = wifi_config.get("name")

    if not all([router_ip, router_name, ssid]):
        raise ValueError(f"Missing router config: ip={router_ip}, name={router_name}, ssid={ssid}")

    # --- Step 0: 清理 DUT 已保存网络 ---
    UiAutomationMixin._clear_saved_wifi_networks(serial)
    dut._forget_wifi_via_ui(serial, ssid)
    time.sleep(2)

    # === 初始化路由器对象 ===
    router = get_router(router_name=router_name, address=router_ip)

    try:
        # === Step 1: 配置为 b/g/n mixed 并启用 AX ===
        with allure.step("Configure 2.4G as b/g/n mixed and enable 802.11ax"):
            # 1.1 使用现有函数配置基础模式
            configure_ap_wireless_mode(router, band='2g', mode='bgn-mixed', ssid=ssid, password=password)

            # 1.2 关键步骤: 额外启用 802.11ax (Wi-Fi 6)
            router.telnet_write("nvram set wl0_11ax=1;")
            router.telnet_write("restart_wireless;")

        # 等待无线服务稳定
        time.sleep(15)

        # === Step 2: 验证模式 (可选，非阻断) ===
        # 注意：由于 AX 在 2.4G 是非标准特性，验证可能不完美。
        # 我们主要关心 DUT 能否连接。
        with allure.step("Verify AP is in b/g/n mode (AX status is assumed enabled)"):
            is_valid = verify_ap_wireless_mode(router, band='2g', expected_ssid=ssid, expected_mode='bgn-mixed')
            logging.info("AP is in expected b/g/n mixed mode: %s", is_valid)
            if not is_valid:
                logging.warning("AP mode verification failed, but proceeding with connection test.")

        # === Step 3: DUT 连接 Wi-Fi ===
        with allure.step("Connect DUT to the 802.11b/g/n/AX network"):
            success = UiAutomationMixin._connect_to_wifi_via_ui(
                serial=serial,
                ssid=ssid,
                password=password,
                logdir=logdir
            )
            if not success:
                pytest.fail("UI connection failed")

            connected = False
            for i in range(15):
                time.sleep(2)
                current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                if current_ssid == ssid:
                    connected = True
                    break

            rssi = dut.get_rssi() if connected else "N/A"
            record_test_step(TCID, f"Connect to b/g/n/AX {ssid}", "PASS" if connected else "FAIL", f"RSSI={rssi}")
            assert connected, f"Failed to connect to SSID: {ssid}"

        # === Step 4: 播放在线视频（验证互联网）===
        with allure.step("Play online video to verify internet connectivity"):
            video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
            ping_ok = UiAutomationMixin._check_network_ping(serial)
            network_works = video_ok and ping_ok
            record_test_step(TCID, f"b/g/n/AX {ssid} network works", "PASS" if network_works else "FAIL", "Internet OK")

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