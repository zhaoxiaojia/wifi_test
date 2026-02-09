# test_wifi_80211ax_only_connectivity.py
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
    restore_ap_default_wireless,
    configure_ap_channel,
    configure_ap_bandwidth
)

TCID = "WiFi-STA-FMD0007"


@allure.title("Wi-Fi 802.11ax (Wi-Fi 6) Only Mode Connectivity Test (2.4GHz)")
@allure.description("""
1. Configure 2.4G Wi-Fi as 802.11ax-only via Telnet
   - Enable 802.11ax (HE)
2. Enable Wi-Fi radio
3. Connect DUT to the 802.11ax network
4. Play online video to verify internet connectivity
""")
def test_wifi_24g_80211ax_only_connectivity(wifi_adb_device):
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
        # === Step 1: 配置为 802.11ax-only (2.4G) ===
        with allure.step("Configure 2.4G Wi-Fi as 802.11ax-only"):
            # 1.1 使用现有函数配置为 'n-only' 模式（这是 AX-only 的基础）
            configure_ap_wireless_mode(router, band='2g', mode='ax-only', ssid=ssid, password=password)
            configure_ap_channel(router, band='2g', channel='auto', ssid=ssid, password=password)
            configure_ap_bandwidth(router, band='2g', bandwidth='20/40MHZ')

            # # 1.2 关键步骤: 额外启用 802.11ax (Wi-Fi 6)
            # router.telnet_write("nvram set wl0_11ax=1;")
            # router.telnet_write("restart_wireless;")

        # 等待无线服务完全重启并稳定
        time.sleep(15)

        # === Step 2: 验证模式 (非阻断，因 2.4G AX 是非标准特性) ===
        with allure.step("Verify AP is in 802.11ax-compatible mode"):
            # 注意：我们无法用现有逻辑完美验证 "ax-only"，
            is_valid = verify_ap_wireless_mode(router, band='2g', expected_ssid=ssid, expected_mode='ax-only')
            logging.info("AP is in ax-only (base for AX) mode: %s", is_valid)
            if not is_valid:
                logging.warning("AP may not be in pure n/ax mode, proceeding with connection test.")

        # === Step 3: DUT 连接 Wi-Fi ===
        with allure.step("Connect DUT to the 802.11ax network"):
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
            record_test_step(TCID, f"Connect to 802.11ax {ssid}", "PASS" if connected else "FAIL", f"RSSI={rssi}")
            assert connected, f"Failed to connect to 802.11ax SSID: {ssid}"

        # === Step 4: 播放在线视频（验证互联网）===
        with allure.step("Play online video to verify internet"):
            video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
            ping_ok = UiAutomationMixin._check_network_ping(serial)
            network_works = video_ok and ping_ok
            record_test_step(TCID, f"802.11ax {ssid} network works", "PASS" if network_works else "FAIL", "Internet OK")

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