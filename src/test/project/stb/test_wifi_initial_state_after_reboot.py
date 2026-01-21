# test_wifi_initial_state_after_reboot.py
import pytest
import allure
import time, logging
import os
from pathlib import Path
from src.util.constants import load_config
from src.tools.connect_tool.duts.android import android
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin
from src.conftest import record_test_step

TCID = "WiFi-STA-FDF0002"

@allure.title("Wi-Fi Initial State Validation")
@allure.description("Reboot DUT, then verify Wi-Fi initial state.")
def test_wifi_initial_state(wifi_adb_device):
    dut, serial, logdir = wifi_adb_device
    all_steps_passed = True
    step_results = []

    # ==============================
    # 🔁 STEP 1: Reboot DUT
    # ==============================
    with allure.step("Step 1: Reboot DUT and wait for boot completion"):
        # Wait for full boot
        booted, boot_debug = dut.wait_for_device_boot(serial, timeout=150)
        details = f"Reboot and boot: {'SUCCESS' if booted else 'FAILED'}\n{boot_debug}"
        passed = "PASS" if booted else "FAIL"

        record_test_step(TCID, "DUT Reboot", passed, details)

        # Attach boot debug log
        allure.attach(boot_debug, name="Boot Debug Log", attachment_type=allure.attachment_type.TEXT)
        if not passed:
            all_steps_passed = False

        if not booted:
            pytest.fail("Device did not boot successfully after reboot")
            logging.info("=== BOOT DEBUG LOG ===")
            logging.info(boot_debug)
            logging.info("======================")

        time.sleep(30)

    # --- Step 2: Wi-Fi enabled ---
    with allure.step("Step 2: Check if Wi-Fi is enabled"):
        enabled = UiAutomationMixin._get_wifi_state_adb(serial)
        passed = enabled is True
        details = "Wi-Fi is ON" if passed else "Wi-Fi is OFF"
        record_test_step(TCID, "Wi-Fi enabled", "PASS" if passed else "FAIL", details)
        img1 = dut._capture_screenshot(logdir, "step1_wifi_enabled")
        if img1 and img1.exists():
            allure.attach.file(str(img1), name="Screenshot - Wi-Fi Enabled", attachment_type=allure.attachment_type.PNG)
        if not passed:
            all_steps_passed = False

    # --- Step 3: Not connected ---
    with allure.step("Step 3: Verify no Wi-Fi network is connected"):
        ssid = dut.get_connected_ssid_adb(serial=serial)
        passed = not ssid
        details = f"Connected to '{ssid}'" if ssid else "Not connected (as expected)"
        record_test_step(TCID, "Not connected to any network", "PASS" if passed else "FAIL", details)
        img2 = dut._capture_screenshot(logdir, "step2_not_connected")
        if img2 and img2.exists():
            allure.attach.file(str(img2), name="Screenshot - Network Status", attachment_type=allure.attachment_type.PNG)
        if not passed:
            all_steps_passed = False

    # --- Step 4: No wired connection ---
    with allure.step("Step 4: Verify no wired connection"):
        is_wired_active, adb_debug = dut.is_wired_connection_active(serial)
        passed = not is_wired_active
        details = "No active wired connection" if passed else f"Wired active: {', '.join(is_wired_active)}"
        record_test_step(TCID, "No wired connection", "PASS" if passed else "FAIL", details)
        if not passed:
            all_steps_passed = False

    # --- Step 5: Scan networks ---
    with allure.step("Step 5: Scan and detect Wi-Fi networks"):
        if not UiAutomationMixin._open_wifi_settings_page(serial):
            logging.warning("Failed to open Wi-Fi settings page, proceeding anyway...")
        time.sleep(4)
        ssids = dut.wifi_wait_for_networks(timeout=12)
        count = len(ssids)
        img4 = dut._capture_screenshot(logdir, "step4_scan_networks")
        if img4 and img4.exists():
            allure.attach.file(str(img4), name="Screenshot - Wi-Fi Scan", attachment_type=allure.attachment_type.PNG)
        passed = count > 0
        details = str(ssids) if ssids else "No networks found"
        record_test_step(TCID, f"Detected {count} networks", "PASS" if passed else "FAIL", details)
        if not passed:
            all_steps_passed = False