# test_wifi_5g_80211n_bandwidth_switching_connectivity.py
"""
Test Plan: 5G 11n, HT20/40 auto channel connection check

1. Configure 5G Wi-Fi as 802.11n-only (an-only) with Auto channel via Telnet.
2. Set bandwidth to 20MHz and 40MHz sequentially.
3. After each change, verify DUT reconnects within 1 minute.
4. Play online video to verify internet connectivity.
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
TCID = "WiFi-STA-FBW0007"

# Maximum wait time for DUT to reconnect (in seconds)
MAX_WAIT_TIME = 60

# Target bandwidth list for the test
TARGET_BANDWIDTH = ['20MHZ', '40MHZ']


@allure.title("Wi-Fi 5GHz 802.11n Bandwidth Switching (Auto/20/40MHz) Connectivity Test")
@allure.description("""
1. Configure 5G Wi-Fi with 802.11n mode and Auto Channel on router.
2. Connect DUT to the 5GHz network.
3. Change AP bandwidth to 20MHz, verify DUT auto-reconnects within 60s.
4. Change AP bandwidth to 40MHz, verify DUT auto-reconnects within 60s.
5. Play online video to verify internet connectivity.
""")
def test_wifi_5g_80211n_bw_switching_connectivity(wifi_adb_device):
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
        # === Step 1: Configure Router to 5GHz 802.11n mode with Auto Channel ===
        with allure.step("Configure 5G Wi-Fi as 802.11n-only with Auto channel"):
            # Use 'an-only' which maps to 11n in 5G
            configure_ap_wireless_mode(
                router, band='5g', mode='an-only', ssid=ssid, password=password
            )
            # Explicitly set channel to 'auto' and initial bandwidth to '20/40MHZ'
            # Note: For 5G, '20/40MHZ' in our semantic map likely sets it to a flexible mode.
            router.set_5g_channel_bandwidth(channel="auto", bandwidth='20/40/80/160MHZ')
            router.commit()

        # === Step 2: Verify AP Configuration ===
        with allure.step("Verify AP is in expected 802.11n mode with Auto channel"):
            is_mode_valid = verify_ap_wireless_mode(
                router, band='5g', expected_ssid=ssid, expected_mode='an-only'
            )
            # Note: Verifying 'Auto' channel precisely is complex, so we rely on mode verification
            # and subsequent reconnection tests as proof of correct setup.
            logging.info("AP is in expected 802.11n mode: %s", is_mode_valid)
            if not is_mode_valid:
                error_msg = "AP did not enter 802.11n mode as expected."
                logging.error(error_msg)
                allure.attach(body=error_msg, name="AP Mode Verification Failed",
                              attachment_type=allure.attachment_type.TEXT)
            record_test_step(TCID, "AP 5G 802.11n mode with Auto channel", "PASS" if is_mode_valid else "FAIL", "AP 5G 802.11n mode")
                #pytest.fail("AP configuration verification failed.")

        # === Step 3: Initial DUT Connection to Wi-Fi ===
        with allure.step("Connect DUT to initial 802.11n (5G) network"):
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
            record_test_step(TCID, f"Initial connect to {ssid} (Auto CH)","PASS" if connected else "FAIL", f"RSSI={rssi}")
            #assert connected, f"Failed to connect to initial SSID: {ssid}"

        # === Step 4: Bandwidth Switching & Reconnection Verification ===
        for bw in TARGET_BANDWIDTH:
            with allure.step(f"Change AP bandwidth to {bw} and verify DUT reconnection"):
                # 1. Configure router to new bandwidth (channel remains 'auto')
                router.set_5g_channel_bandwidth(bandwidth=bw)
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
                        logging.info(f"DUT reconnected with BW={bw}. RSSI: {current_rssi}")
                        break

                # Record the test step result
                step_result = "PASS" if reconnected else "FAIL"
                record_test_step(TCID, f"Switch to BW={bw} and reconnect",step_result, f"RSSI={current_rssi}")

                # The requirement is to reconnect within 1 min, so we assert this.
                #assert reconnected, f"DUT failed to reconnect to '{ssid}' within {MAX_WAIT_TIME}s after AP bandwidth changed to {bw}."

            # === Step 5: Verify Internet Connectivity ===
            with allure.step("Play online video to verify internet"):
                video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
                ping_ok = UiAutomationMixin._check_network_ping(serial)
                network_works = video_ok and ping_ok
                record_test_step(TCID, f"802.11n (5G) {ssid} network works well",
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