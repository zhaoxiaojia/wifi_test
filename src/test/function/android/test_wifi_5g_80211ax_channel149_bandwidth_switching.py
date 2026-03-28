# test_wifi_5g_80211ax_channel149_bandwidth_switching.py
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
    verify_ap_channel_and_beacon,
    restore_ap_default_wireless,
)

TCID = "WiFi-STA-FBW0004"
MAX_WAIT_TIME = 60
TARGET_BANDWIDTH = ['20MHZ', '40MHZ', '80MHZ']

@allure.title("Wi-Fi 5GHz 802.11ax Channel 149 Bandwidth Switching (20/40/80MHz) Connectivity Test")
@allure.description("""
1. Configure 5G Wi-Fi on channel 149 with 802.11ax mode via Telnet.
2. Set bandwidth to 20MHz, 40MHz, and 80MHz sequentially.
3. After each change, verify DUT reconnects within 1 minute.
4. Play online video to verify internet connectivity.
""")
def test_wifi_5g_80211ax_ch149_bw_switching_connectivity(wifi_adb_device):
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

    # 定义要测试的频宽列表
    target_bandwidths = TARGET_BANDWIDTH

    # === 初始化路由器对象 ===
    router = get_router(router_name=router_name, address=router_ip)

    try:
        # === Step 1: 配置路由器为 5GHz 802.11ax 模式，并设置信道为 149 ===
        with allure.step("Configure 5G Wi-Fi as 802.11ax on channel 149"):
            configure_ap_wireless_mode(router, band='5g', mode='ax-mixed', ssid=ssid, password=password)
            # 初始频宽设为20MHz
            router.set_5g_channel_bandwidth(channel=149, bandwidth='20/40/80/160MHZ')
            router.commit()


        # === Step 2: 验证AP配置 ===
        with allure.step("Verify AP is in expected 802.11ax mode on channel 149"):
            is_mode_valid = verify_ap_wireless_mode(router, band='5g', expected_ssid=ssid, expected_mode='ax-mixed')
            is_channel_valid = verify_ap_channel_and_beacon(router, band='5g', expected_channel=149, expected_ssid=ssid)
            is_valid = is_mode_valid and is_channel_valid
            logging.info("AP is in expected 802.11ax mode on channel 149: %s", is_valid)
            if not is_valid:
                error_msg = (
                    f"AP did not enter 802.11ax mode or is not on channel 149 as expected.\n"
                    f"Mode valid: {is_mode_valid}, Channel valid: {is_channel_valid}"
                )
                logging.error(error_msg)
                allure.attach(body=error_msg, name="AP Configuration Verification Failed", attachment_type=allure.attachment_type.TEXT)
                record_test_step(TCID, f"AP config verification failed – aborting test", "FAIL", "FAILED")
                pytest.fail("AP configuration verification failed – aborting test.")

        # === Step 3: DUT 初始连接 Wi-Fi ===
        with allure.step("Connect DUT to initial 802.11ax (5G) network on channel 149 (20MHz)"):
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
            record_test_step(TCID, f"Initial connect to {ssid} on CH149 (Auto)", "PASS" if connected else "FAIL", f"RSSI={rssi}")
            assert connected, f"Failed to connect to initial 802.11ax (5G) SSID: {ssid}"

        # === Step 4: 频宽切换与重连验证 ===
        for bw in target_bandwidths:
            with allure.step(f"Change AP bandwidth to {bw} and verify DUT reconnection"):
                # 1. 配置路由器到新频宽
                router.set_5g_channel_bandwidth(channel=149, bandwidth=bw)
                router.commit()
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
                #assert reconnected, f"DUT failed to reconnect to '{ssid}' within 1 minute after AP bandwidth changed to {bw}."

            # === Step 5: 播放在线视频（验证互联网）===
            with allure.step("Play online video to verify internet"):
                video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
                ping_ok = UiAutomationMixin._check_network_ping(serial)
                network_works = video_ok and ping_ok
                record_test_step(TCID, f"802.11ax (5G) {ssid} on CH149 network works well", "PASS" if network_works else "FAIL", f"Network work well")

    finally:
        # === Step 6: 恢复 AP 默认设置 ===
        with allure.step("Restore AP to default"):
            restore_ap_default_wireless(
                router, band='5g',
                original_ssid=wifi_config.get("5g_ssid"),
                original_password=wifi_config.get("password")
            )
            record_test_step(TCID, "Restore AP to default", "PASS", "Environment cleaned up")
            router.quit()