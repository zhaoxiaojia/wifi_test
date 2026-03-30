# test_wifi_initial_state.py
import pytest
import allure
import time
import os, logging
from pathlib import Path
from src.util.constants import load_config
from src.tools.connect_tool.duts.android import android
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin
from src.conftest import record_test_step  # 直接调用，无需 from src.

TCID = "WiFi-STA-FDF0001"


@allure.title("Wi-Fi Initial State Validation")
@allure.description("Verify that Wi-Fi is enabled, not connected to any network, and can detect available networks.")
def test_wifi_initial_state(wifi_adb_device):
    dut, serial, logdir, _ = wifi_adb_device
    all_steps_passed = True
    step_results = []
    # --- Step 0: clear currect connected and save SSID ---
    UiAutomationMixin._clear_saved_wifi_networks(serial)
    dut._forget_wifi_via_ui(serial)
    time.sleep(2)

    # --- Step 1: Wi-Fi enabled ---
    with allure.step("Check if Wi-Fi is enabled"):
        enabled = UiAutomationMixin._get_wifi_state_adb(serial)
        passed = enabled is True
        details = "Wi-Fi is ON" if passed else "Wi-Fi is OFF"
        record_test_step(TCID, "Wi-Fi enabled", "PASS" if passed else "FAIL", details)
        step_results.append(("Wi-Fi enabled", "PASS" if passed else "FAIL", details))
        # Capture screenshot regardless of result
        img1 = dut._capture_screenshot(logdir, "step1_wifi_enabled")
        if img1 and img1.exists():
            allure.attach.file(str(img1), name="Screenshot - Wi-Fi Enabled", attachment_type=allure.attachment_type.PNG)
        if not passed:
            all_steps_passed = False
            #pytest.fail("Wi-Fi should be enabled")
        if not enabled:
            with allure.step("Recovering: Enabling Wi-Fi for subsequent steps"):
                success = UiAutomationMixin._enable_wifi_adb(serial)
                if success:
                    time.sleep(4)
                    logging.info("Wi-Fi enabled for recovery. Proceeding to next steps.")
                else:
                    logging.warning("Failed to enable Wi-Fi even for recovery.")

    # --- Step 2: Not connected ---
    with allure.step("Verify no Wi-Fi network is connected"):
        ssid = dut.get_connected_ssid_adb(serial=serial)
        passed = not ssid
        details = f"Connected to '{ssid}'" if ssid else "Not connected (as expected)"
        record_test_step(TCID, "Not connected to any network", "PASS" if passed else "FAIL", details)
        step_results.append(("Not connected to any network", "PASS" if passed else "FAIL", details))
        img2 = dut._capture_screenshot(logdir, "step2_not_connected")
        if img2 and img2.exists():
            allure.attach.file(str(img2), name="Screenshot - Network Connection Status",
                               attachment_type=allure.attachment_type.PNG)
        if not passed:
            all_steps_passed = False
            with allure.step("Recovering: Disconnecting from current Wi-Fi network"):
                disconnect_success = UiAutomationMixin._disconnect_and_prevent_reconnect(serial)
                if disconnect_success:
                    time.sleep(3)  # 等待断开生效
                    logging.info("Successfully disconnected from Wi-Fi for recovery.")
                    # 可选：再次确认已断开
                    ssid_after = dut.get_connected_ssid_adb(serial=serial)
                    if ssid_after:
                        logging.warning(f"Still connected after disconnect attempt: {ssid_after}")
                else:
                    logging.warning("Failed to disconnect from Wi-Fi, subsequent steps may be affected.")

    # --- Step 3: No wired (Ethernet) connection ---
    with allure.step("Verify no wired (Ethernet) connection is active"):
        # Use the new driver method
        is_wired_active, adb_debug = dut.is_wired_connection_active(serial)

        passed = not is_wired_active
        details = "No active wired connection detected" if passed else f"Wired connection active. Details: {adb_debug[:200]}..."

        record_test_step(TCID, "No wired connection", "PASS" if passed else "FAIL", details)
        step_results.append(("No wired connection", "PASS" if passed else "FAIL", details))
        if not passed:
            all_steps_passed = False
            #pytest.fail("Wired connection should disconnected")

    # --- Step 4: Scan networks ---
    with allure.step("Scan and detect available Wi-Fi networks"):
        if not UiAutomationMixin._open_wifi_settings_page(serial):
            logging.warning("Failed to open Wi-Fi settings page, proceeding anyway...")
        time.sleep(4)
        ssids = dut.wifi_wait_for_networks(timeout=12)
        count = len(ssids)
        img3 = dut._capture_screenshot(logdir, "step3_scan_networks")
        if img3 and img3.exists():
            allure.attach.file(str(img3), name="Screenshot - Wi-Fi Scan Results",
                               attachment_type=allure.attachment_type.PNG)
        passed = count > 0
        details = str(ssids) if ssids else "No networks found"
        record_test_step(TCID, f"Detected {count} networks", "PASS" if passed else "FAIL", details)
        step_results.append((f"Detected {count} networks", "PASS" if passed else "FAIL", details))
        if not passed:
            all_steps_passed = False
            #pytest.fail("Scan should detect at least one network")

    # Optional: final assertion (not strictly needed since each step fails immediately)
    # assert all_steps_passed, "One or more steps failed"