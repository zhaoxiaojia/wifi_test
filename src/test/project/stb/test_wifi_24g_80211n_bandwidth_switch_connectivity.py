# test_wifi_2g_80211n_bandwidth_switch_connectivity.py

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
    verify_ap_channel_and_beacon,
    configure_ap_bandwidth,
    restore_ap_default_wireless
)

TCID = "WiFi-STA-FBW0005"  # 请根据您的实际用例编号规则调整
MAX_WAIT_TIME = 60
TARGET_BANDWIDTH = ['20MHZ', '40MHZ']

@allure.title("Wi-Fi 2.4GHz 802.11n Bandwidth Switch (Auto/20M/40M) Connectivity Test")
@allure.description("""
1. Configure 2.4G Wi-Fi with 802.11n-only mode and Auto Channel on router.
2. Connect DUT to the 2.4GHz network.
3. Change AP bandwidth to 20MHz, verify DUT auto-reconnects within 60s.
4. Change AP bandwidth to 40MHz, verify DUT auto-reconnects within 60s.
5. Play online video to verify internet connectivity.
""")
def test_wifi_2g_80211n_bandwidth_switch_connectivity(wifi_adb_device):
    dut, serial, logdir, cfg = wifi_adb_device

    # === 从配置中提取路由器参数 ===
    wifi_config = cfg.get("router", {})
    ssid = wifi_config.get("24g_ssid")  # 使用 2.4G SSID
    password = wifi_config.get("password", "88888888")
    security = wifi_config.get("security_mode", "WPA2-Personal")
    router_ip = wifi_config.get("address")
    router_name = wifi_config.get("name")
    target_bandwidths = TARGET_BANDWIDTH
    logging.info(f"SSID: {ssid}")

    if not all([router_ip, router_name]):
        raise ValueError(f"Missing router config: ip={router_ip}, name={router_name}")

    # --- Step 0: 清理 DUT 已保存网络 ---
    UiAutomationMixin._clear_saved_wifi_networks(serial)
    dut._forget_wifi_via_ui(serial, ssid)
    time.sleep(2)

    # === 初始化路由器对象 ===
    router = get_router(router_name=router_name, address=router_ip)

    try:
        # === Step 1: 配置路由器为 2.4GHz 802.11n-only 模式，并设置信道为 Auto ===
        with allure.step("Configure 2.4G Wi-Fi as 802.11n-only on Auto Channel"):
            # 1. 设置无线模式为 'n-only' (2.4G 802.11n)
            configure_ap_wireless_mode(router, band='2g', mode='n-only', ssid=ssid, password=password)
            # 2. 设置信道为 Auto (通常 channel=0 或不设置)
            configure_ap_channel(router, band='2g', channel='auto', ssid=ssid, password=password)
            configure_ap_bandwidth(router, band='2g', bandwidth='20/40MHZ')

        # === Step 2: 验证 AP 配置 ===
        with allure.step("Verify AP is in expected 802.11n-only mode on Auto Channel"):
            is_mode_valid = verify_ap_wireless_mode(router, band='2g', expected_ssid=ssid, expected_mode='n-only')
            is_beacon_valid = verify_ap_channel_and_beacon(router, band='2g', expected_ssid=ssid)

            is_valid = is_mode_valid and is_beacon_valid
            if not is_valid:
                error_msg = f"AP config verification failed. Mode: {is_mode_valid}, Beacon: {is_beacon_valid}"
                logging.error(error_msg)
                allure.attach(body=error_msg, name="AP Config Verification Failed",
                              attachment_type=allure.attachment_type.TEXT)
            record_test_step(TCID, "AP config for 2.4G 11n Auto", "PASS" if is_valid else "FAIL", "24g_11N_Auto")
                #pytest.fail("AP configuration verification failed.")

        # === Step 3: DUT 连接 Wi-Fi (Auto Channel) ===
        with allure.step("Connect DUT to 802.11n (2.4G) network on Auto Channel"):
            success = UiAutomationMixin._connect_to_wifi_via_ui(
                serial=serial, ssid=ssid, password=password, logdir=logdir
            )
            connected = False
            for i in range(15):
                time.sleep(2)
                current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                if current_ssid == ssid:
                    connected = True
                    break
            rssi = dut.get_rssi() if connected else "N/A"
            record_test_step(TCID, f"Connect to 802.11n (2.4G) {ssid} on Auto CH", "PASS" if connected else "FAIL",
                             f"RSSI={rssi}")
            #assert connected, f"Failed to connect to 802.11n (2.4G) SSID: {ssid}"

        # === Step 4: 切换频宽到 20/40MHz 并验证自动重连 ===
        for bw in target_bandwidths:
            with allure.step(f"Change AP bandwidth to {bw} and verify DUT reconnection"):
                # 1. 配置路由器到新频宽
                # router.set_2g_bandwidth(width=bw)
                # router.commit()
                configure_ap_bandwidth(router, band='2g', bandwidth=bw)
                time.sleep(5)  # 给路由器一点时间应用配置

                # 2. 等待并验证DUT重连 (最多60秒)
                reconnected = False
                max_wait_time = MAX_WAIT_TIME  # 1分钟
                start_time = time.time()
                current_rssi = "N/A"

                is_saved = UiAutomationMixin.is_wifi_network_saved(serial, ssid)
                if is_saved:
                    logging.info(f"SSID Disconnect and in Saved list")
                else:
                    logging.info(f"SSID Disconnect and not in Saved list")

                while time.time() - start_time < max_wait_time:
                    time.sleep(2)
                    current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                    if current_ssid == ssid:
                        reconnected = True
                        current_rssi = dut.get_rssi()
                        logging.info(f"DUT reconnected with BW={bw}. RSSI: {current_rssi}")
                        break

                # 记录测试步骤结果
                step_result = "PASS" if reconnected else "FAIL"
                record_test_step(TCID, f"Switch to BW={bw} and reconnect", step_result, f"RSSI={current_rssi}")
                # assert reconnected, f"DUT failed to reconnect to '{ssid}' within 1 minute after AP bandwidth changed to {bw}."

            # === Step 5: 播放在线视频（验证互联网）===
            with allure.step("Play online video to verify internet"):
                video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
                ping_ok = UiAutomationMixin._check_network_ping(serial)
                network_works = video_ok and ping_ok
                record_test_step(TCID, f"802.11ax (5G) {ssid} on CH52 network works well",
                                 "PASS" if network_works else "FAIL", f"Network work well")


    finally:
        # === Step 7: 恢复 AP 默认设置 ===
        with allure.step("Restore AP to default"):
            restore_ap_default_wireless(
                router, band='2g',
                original_ssid=wifi_config.get("24g_ssid"),
                original_password=wifi_config.get("password")
            )
            record_test_step(TCID, "Restore AP to default", "PASS", "Environment cleaned up")
        router.quit()


# --- Helper Function: Wait for Auto-Reconnect ---
def _wait_for_auto_reconnect(dut, serial: str, target_ssid: str, timeout: int = 60) -> bool:
    """
    Waits for the DUT to automatically reconnect to a 'Saved' network.

    It first confirms the network is saved, then waits for it to become connected.
    """
    from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin

    # 1. Confirm the network is in 'Saved' state (using our new robust method)
    if not UiAutomationMixin.is_wifi_network_saved(serial, target_ssid):
        logging.error(f"Network '{target_ssid}' is not in 'Saved' state. Cannot expect auto-reconnect.")
        return False

    # 2. Wait for it to become 'Connected'
    start_time = time.time()
    while time.time() - start_time < timeout:
        current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
        if current_ssid == target_ssid:
            logging.info(f"✅ Auto-reconnected to '{target_ssid}' at {time.time() - start_time:.2f}s")
            return True
        time.sleep(2)

    logging.error(f"❌ Failed to auto-reconnect to '{target_ssid}' within {timeout} seconds.")
    return False