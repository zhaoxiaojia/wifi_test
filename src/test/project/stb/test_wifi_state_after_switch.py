# test_wifi_state_after_switch.py

import pytest
import allure
import time
import logging
from pathlib import Path
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin
from src.conftest import record_test_step

TCID = "WiFi-STA-FMN0003"


@allure.title("Wi-Fi State When Switch ON/OFF")
@allure.description(
    "1. Disable Wi-Fi and verify no networks are detected. 2. Enable Wi-Fi and verify networks are detected.")
def test_wifi_state_after_switch(wifi_adb_device):
    dut, serial, logdir, _  = wifi_adb_device
    all_steps_passed = True

    # ==============================
    # Step 1: Disable Wi-Fi and Verify No Networks Detected
    # ==============================
    with allure.step("Disable Wi-Fi and verify no networks"):
        try:
            # Disable Wi-Fi
            success_disable = UiAutomationMixin._disable_wifi_adb(serial)
            if not success_disable:
                success_disable = UiAutomationMixin._disable_wifi_adb(serial)  # retry

            wifi_disabled = success_disable and not UiAutomationMixin._get_wifi_state_adb(serial)
            if not wifi_disabled:
                raise Exception("Failed to disable Wi-Fi or still ON")

            # Wait for a short period to ensure the change takes effect
            time.sleep(3)

            # Force open Wi-Fi settings page for screenshot
            if not UiAutomationMixin._open_wifi_settings_page(serial):
                logging.warning("Failed to open Wi-Fi settings page, proceeding anyway...")
            time.sleep(4)

            # Check for networks
            ssids = dut.wifi_wait_for_networks(timeout=8)
            no_networks = len(ssids) == 0

            if not no_networks:
                raise Exception(f"Unexpected networks found when Wi-Fi is OFF: {ssids}")

            details = "Wi-Fi disabled and no networks detected"
            status = "PASS"
            record_test_step(TCID, "Disable Wi-Fi and Verify No Networks", status, details)

        except Exception as e:
            details = f"Exception during disable and scan check (OFF): {str(e)}"
            record_test_step(TCID, "Disable Wi-Fi and Verify No Networks", "FAIL", details)
            all_steps_passed = False
            logging.exception(details)

        # Screenshot after disable and scan check
        img1 = dut._capture_screenshot(logdir, "step1_wifi_disabled_and_scan_off")
        if img1 and img1.exists():
            allure.attach.file(str(img1), name="Screenshot - Wi-Fi Disabled and Scan Result (Wi-Fi OFF)",
                               attachment_type=allure.attachment_type.PNG)

    # ==============================
    # Step 2: Enable Wi-Fi and Verify Networks Detected
    # ==============================
    with allure.step("Enable Wi-Fi and verify networks"):
        try:
            # Enable Wi-Fi
            success_enable = UiAutomationMixin._enable_wifi_adb(serial)
            if not success_enable:
                success_enable = UiAutomationMixin._enable_wifi_adb(serial)  # retry

            wifi_enabled = success_enable and UiAutomationMixin._get_wifi_state_adb(serial)
            if not wifi_enabled:
                raise Exception("Failed to enable Wi-Fi or still OFF")

            # Wait for a short period to ensure the change takes effect
            time.sleep(4)

            # Force open Wi-Fi settings page for screenshot
            if not UiAutomationMixin._open_wifi_settings_page(serial):
                logging.warning("Failed to open Wi-Fi settings page, proceeding anyway...")
            time.sleep(4)

            # Check for networks
            ssids = dut.wifi_wait_for_networks(timeout=12)
            has_networks = len(ssids) > 0

            if not has_networks:
                raise Exception("No networks found when Wi-Fi is ON (unexpected)")

            details = f"Wi-Fi enabled and networks detected: {ssids}"
            status = "PASS"
            record_test_step(TCID, "Enable Wi-Fi and Verify Networks", status, details)

        except Exception as e:
            details = f"Exception during enable and scan check (ON): {str(e)}"
            record_test_step(TCID, "Enable Wi-Fi and Verify Networks", "FAIL", details)
            all_steps_passed = False
            logging.exception(details)

        # Screenshot after enable and scan check
        img2 = dut._capture_screenshot(logdir, "step2_wifi_enabled_and_scan_on")
        if img2 and img2.exists():
            allure.attach.file(str(img2), name="Screenshot - Wi-Fi Enabled and Scan Result (Wi-Fi ON)",
                               attachment_type=allure.attachment_type.PNG)

    # Final assertion
    if not all_steps_passed:
        pytest.fail("One or more steps failed. See Excel report for details.")