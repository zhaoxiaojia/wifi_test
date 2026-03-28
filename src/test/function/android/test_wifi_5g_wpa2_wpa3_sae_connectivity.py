# test_wifi_5g_wpa2_wpa3_sae_connectivity.py
"""

Precondition:
1. WiFi is ON on DUT, not connected to any network.
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
    configure_ap_channel,
    configure_ap_security_universal,  # <-- Our new function
    restore_ap_default_wireless
)

TCID = "WiFi-STA-FSM00262"
PASSWORD = "88888888"  # 10-digit hex key for WEP-64


@allure.title("Wi-Fi 5G WPA2_WPA3-SAE Connectivity Test")
@allure.description("""
1. Configure Wi-Fi 5G with WPA2_WPA3-SAE encryption on router.
2. Connect DUT to the wpa2_wpa3 network via UI with the correct password.
3. Verify internet connectivity by playing an online video.
""")
def test_wifi_wpa2_wpa3_sae_connectivity(wifi_adb_device):
    dut, serial, logdir, cfg = wifi_adb_device

    # === Extract router config from testbed.yaml ===
    wifi_config = cfg.get("router", {})
    router_ip = wifi_config.get("address")
    router_name = wifi_config.get("name")
    #password = wifi_config.get("password", "88888888")
    password = PASSWORD
    band_list = {'5g'} #'
    ssid_list = {}
    ssid_list['5g'] = wifi_config.get("5g_ssid")
    #ssid_list['5g'] = wifi_config.get("5g_ssid")

    if not all([router_ip, router_name, ssid_list]):
        raise ValueError(f"Missing router config: ip={router_ip}, name={router_name}, ssid={ssid_list}")

    # === Initialize router object ===
    router = get_router(router_name=router_name, address=router_ip)
    try:
        for band in band_list:
            # --- Step 0: Ensure clean state on DUT ---
            with allure.step("Ensure DUT is in a clean state (WiFi ON, no saved networks)"):
                # The 'wifi_adb_device' fixture usually ensures WiFi is ON.
                # We just need to clear any previously saved networks.
                UiAutomationMixin._clear_saved_wifi_networks(serial)
                for ssid in ssid_list:
                    dut._forget_wifi_via_ui(serial, ssid_list[band])
                time.sleep(2)


            # === Step 1: Configure Router for WPA2-PSK&AES  ===
            with allure.step(f"Configure AP {band} with wpa2_wpa3-SAE security"):
                # Set SSID and channel first, Need Legacy mode to enable WEP setting
                configure_ap_wireless_mode(
                    router, band=band, mode='auto', ssid=ssid_list[band], password=password
                )

                # Use our new unified function to set WEP security
                configure_ap_security_universal(
                    router,
                    band=band,
                    security_mode='WPA2/WPA3-Personal',
                    password=password
                )

                time.sleep(10)  # Give AP time to broadcast the new WEP network

            # === Step 2: Connect DUT via UI ===
            with allure.step("Connect DUT to wpa2_wpa3-SAE network via UI"):
                # Use the existing UI mixin to perform the connection flow
                success = UiAutomationMixin._connect_to_wifi_via_ui(
                    serial=serial,
                    ssid=ssid_list[band],
                    password=password,
                    logdir=logdir
                )

                # Verify connection status
                connected = False
                for _ in range(15):  # Wait up to ~30 seconds
                    time.sleep(2)
                    current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                    if current_ssid == ssid_list[band]:
                        connected = True
                        break

                rssi = dut.get_rssi() if connected else "N/A"
                record_test_step(
                    TCID,
                    f"Connect to wpa2_wpa3-SAE{ssid_list[band]}",
                    "PASS" if connected else "FAIL",
                    f"RSSI={rssi}"
                )
                assert connected, f"Failed to connect to WPA2_WPA3-PSK&AES: {ssid_list[band]}"

            # === Step 3: Verify Internet Connectivity ===
            with allure.step("Play online video to verify internet connectivity"):
                # Launch YouTube and perform a search/playback
                video_ok = dut.launch_youtube_tv_and_search(serial, logdir)
                # Also perform a simple ping check as a backup
                ping_ok = UiAutomationMixin._check_network_ping(serial)

                network_works = video_ok and ping_ok
                record_test_step(
                    TCID,
                    "WPA2-PSK&AES network internet works",
                    "PASS" if network_works else "FAIL",
                    "YouTube playable and ping successful" if network_works else "Connectivity failed"
                )
                assert network_works, "Internet connectivity verification failed on wpa2_wpa3-SAE network!"

    finally:
        # === Step 4: Cleanup - Restore AP to default ===
        with allure.step("Restore AP to default settings"):
            restore_ap_default_wireless(
                router,
                band=band,
                original_ssid=ssid_list[band],
                original_password=password
            )
            router.quit()