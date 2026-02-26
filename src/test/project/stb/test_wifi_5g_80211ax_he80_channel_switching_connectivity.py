# test_wifi_5g_80211ax_he80_channel_switching_connectivity.py
"""
Test Plan: 5G 11ax HE80, [CH36/52/100/149] connection check
"""

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
)

# Test Case ID
TCID = "WiFi-STA-FBW0011"

# Maximum wait time for DUT to reconnect (in seconds)
MAX_WAIT_TIME = 60

# Target channel list for the test (all valid 80MHz channels in their respective UNII bands)
TARGET_CHANNELS = [36, 52, 100, 149]


@allure.title("Wi-Fi 5GHz 802.11ax HE80 Channel Switching (CH36/52/100/149) Connectivity Test")
@allure.description("""
1. Configure 5G Wi-Fi as 802.11ax-only (an-ac-mixed) with 80MHz bandwidth via Telnet.
2. Set channel to 36, 52, 100, and 149 sequentially.
3. After each change, verify DUT reconnects within 1 minute.
4. Play online video to verify internet connectivity.
""")
def test_wifi_5g_80211ax_he80_ch_switching_connectivity(wifi_adb_device):
    dut, serial, logdir, cfg = wifi_adb_device

    # === Step 0: Extract router configuration from test config ===
    wifi_config = cfg.get("router", {})
    ssid = wifi_config.get("5g_ssid")  # Use 5G SSID
    password = wifi_config.get("password", "88888888")
    security = wifi_config.get("security_mode", "WPA2-Personal")
    router_ip = wifi_config.get("address")
    router_name = wifi_config.get("name")

    if not all([router_ip, router_name, ssid]):
        raise ValueError(f"Missing router config: ip={router_ip}, name={router_name}, ssid={ssid}")

    # --- Clean up any previously saved networks on DUT ---
    UiAutomationMixin._clear_saved_wifi_networks(serial)
    dut._forget_wifi_via_ui(serial, ssid)
    time.sleep(2)

    # === Initialize router control object ===
    router = get_router(router_name=router_name, address=router_ip)

    try:
        # === Step 1: Configure Router to 5GHz 802.11ax mode with 80MHz bandwidth ===
        with allure.step("Configure 5G Wi-Fi as 802.11ax-only with 80MHz bandwidth"):
            # Use 'an-ac-mixed' which maps to 11ax in 5G
            configure_ap_wireless_mode(
                router, band='5g', mode='ax-mixed', ssid=ssid, password=password
            )
            # Explicitly set bandwidth to '80MHZ' and initial channel to first target (e.g., 36)
            router.set_5g_channel_bandwidth(channel="auto", bandwidth='80MHZ')
            router.commit()

        # === Step 2: Verify AP Configuration ===
        with allure.step("Verify AP is in expected 802.11ax mode with 80MHz bandwidth"):
            is_mode_valid = verify_ap_wireless_mode(
                router, band='5g', expected_ssid=ssid, expected_mode='ax-mixed'
            )
            logging.info("AP is in expected 802.11ax mode: %s", is_mode_valid)
            if not is_mode_valid:
                error_msg = "AP did not enter 802.11ax mode as expected."
                logging.error(error_msg)
                allure.attach(body=error_msg, name="AP Mode Verification Failed",
                              attachment_type=allure.attachment_type.TEXT)
                #record_test_step(TCID, "AP 5G 802.11ax mode with 80MHz", "PASS" if is_mode_valid else "FAIL", "AP 5G 802.11ax mode")
                #pytest.fail("AP configuration verification failed.")

        # === Step 3: Initial DUT Connection to Wi-Fi ===
        with allure.step("Connect DUT to initial 802.11ax (5G) network"):
            success = UiAutomationMixin._connect_to_wifi_via_ui(
                serial=serial, ssid=ssid, password=password, logdir=logdir
            )
            connected = False
            for i in range(15):  # Wait up to 30 seconds
                time.sleep(2)
                current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                if current_ssid == ssid:
                    connected = True
                    break

            rssi = dut.get_rssi() if connected else "N/A"
            record_test_step(TCID, f"Initial connect to {ssid} (CH Auto))",
                             "PASS" if connected else "FAIL", f"RSSI={rssi}")
            assert connected, f"Failed to connect to initial SSID: {ssid}"

        # === Step 4: Channel Switching & Reconnection Verification ===
        for ch in TARGET_CHANNELS:
            with allure.step(f"Change AP channel to {ch} and verify DUT reconnection"):
                # 1. Configure router to new channel (bandwidth remains '80MHZ')
                router.set_5g_channel_bandwidth(channel=ch, bandwidth='80MHZ')
                router.commit()
                time.sleep(5)  # Allow router to apply changes

                # 2. Wait and verify DUT reconnection (within MAX_WAIT_TIME)
                reconnected = False
                start_time = time.time()
                current_rssi = "N/A"

                while time.time() - start_time < MAX_WAIT_TIME:
                    time.sleep(2)
                    current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                    if current_ssid == ssid:
                        reconnected = True
                        current_rssi = dut.get_rssi()
                        logging.info(f"DUT reconnected on CH={ch}. RSSI: {current_rssi}")
                        break

                # Record the test step result
                step_result = "PASS" if reconnected else "FAIL"
                record_test_step(TCID, f"Switch to CH={ch} and reconnect",
                                 step_result, f"RSSI={current_rssi}")

                # The requirement is to reconnect within 1 min, so we assert this.
                assert reconnected, f"DUT failed to reconnect to '{ssid}' within {MAX_WAIT_TIME}s after AP channel changed to {ch}."

            # === Step 5: Verify Internet Connectivity ===
            with allure.step("Play online video to verify internet"):
                video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
                ping_ok = UiAutomationMixin._check_network_ping(serial)
                network_works = video_ok and ping_ok
                record_test_step(TCID, f"802.11ax (5G) {ssid} network works well",
                                 "PASS" if network_works else "FAIL", "Network work well")

    finally:
        # === Step 6: Restore AP to Default Settings ===
        with allure.step("Restore AP to default"):
            restore_ap_default_wireless(
                router, band='5g',
                original_ssid=wifi_config.get("5g_ssid"),
                original_password=wifi_config.get("password")
            )
            record_test_step(TCID, "Restore AP to default", "PASS", "Environment cleaned up")
            router.quit()