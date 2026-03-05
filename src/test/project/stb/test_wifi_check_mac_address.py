# test_wifi_check_mac_address.py
import pytest
import allure
import time
import os, logging
from pathlib import Path
from src.util.constants import load_config
from src.tools.connect_tool.duts.android import android
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin
from src.conftest import record_test_step  # 直接调用，无需 from src.

TCID = "WiFi-STA-FDF0004"


@allure.title("Wi-Fi MAC Address Persistence After Reboot")
@allure.description("Connect to specified SSID, verify IP/MAC, reboot, and ensure MAC remains unchanged.")
def test_wifi_check_mac_address(wifi_adb_device):
    dut, serial, logdir, cfg  = wifi_adb_device
    all_steps_passed = True
    step_results = []

    # === 从配置中获取目标 SSID 和 Router IP ===
    wifi_config = cfg.get("router", {})
    target_ssid = wifi_config.get("24g_ssid")
    target_ssid_pwd = "88888888"
    router_ip = wifi_config.get("address")

    if not target_ssid or not router_ip:
        pytest.fail("Missing 'wifi_test.target_ssid' or 'wifi_test.router_ip' in config")

    with allure.step(f"Target SSID: {target_ssid}, Router IP: {router_ip}"):
        pass

    # --- Step 0: clear currect connected dut save SSID ---
    UiAutomationMixin._clear_saved_wifi_networks(serial)
    dut._forget_wifi_via_ui(serial, target_ssid)

    # === Step 1: Check current Wi-Fi connection ===
    with allure.step(f"Check current Wi-Fi connection"):
        #Make sure Wi-Fi enabled
        enabled = UiAutomationMixin._get_wifi_state_adb(serial)
        if not enabled:
            with allure.step("Recovering: Enabling Wi-Fi for subsequent steps"):
                success = UiAutomationMixin._enable_wifi_adb(serial)
                if success:
                    time.sleep(4)
                    logging.info("Wi-Fi enabled for recovery. Proceeding to next steps.")
                else:
                    logging.warning("Failed to enable Wi-Fi even for recovery.")

        current_ssid = dut.get_connected_ssid_adb(serial)
        if current_ssid == target_ssid:
            logging.info(f"Already connected to target SSID: {target_ssid}. Skipping connection.")
            # 直接进入 Step 2
        else:
            logging.info(f"Current SSID: '{current_ssid}' ≠ target '{target_ssid}'. Proceeding to connect.")

            # --- 执行原连接流程 ---
            with allure.step(f"Connect to SSID via UI: {target_ssid}"):
                success = UiAutomationMixin._connect_to_wifi_via_ui(
                    serial=serial,
                    ssid=target_ssid,
                    password=target_ssid_pwd,  # 开放网络
                    logdir=logdir
                )
                connected = False
                for i in range(15):
                    time.sleep(2)
                    current_ssid = dut.get_connected_ssid_via_cli_adb(serial).strip()
                    if current_ssid == target_ssid:
                        connected = True
                        break

                rssi = dut.get_rssi() if connected else "N/A"
                record_test_step(TCID, f"Connect to Wi-Fi {target_ssid}", "PASS" if connected else "FAIL",
                                 f"RSSI={rssi}")
                step_results.append(("Connect to target SSID", "PASS" if connected else "FAIL", connected))

                img1 = dut._capture_screenshot(logdir, "step1_connected")
                if img1 and img1.exists():
                    allure.attach.file(str(img1), name="Screenshot - Connected",
                                       attachment_type=allure.attachment_type.PNG)

                if not connected:
                    all_steps_passed = False
                    pytest.fail(f"Failed to connect to {target_ssid} via UI")

                time.sleep(5)  # 等待 IP 分配

    # --- Step 2: Check IP (same subnet as router) and get MAC ---
    with allure.step("Verify IP in same subnet and capture MAC"):
        ip_addr = UiAutomationMixin.get_device_ip_adb(serial)
        mac_addr = UiAutomationMixin.get_wifi_mac_adb(serial)

        if not ip_addr or not mac_addr:
            passed = False
            details = f"Failed to get IP or MAC. IP: {ip_addr}, MAC: {mac_addr}"
        else:
            # 判断是否同网段（简单匹配前缀）
            router_prefix = ".".join(router_ip.split(".")[:3])
            ip_prefix = ".".join(ip_addr.split(".")[:3])
            passed = (router_prefix == ip_prefix)
            details = f"IP: {ip_addr}, MAC: {mac_addr}, Router IP: {router_ip} → {'Same subnet' if passed else 'Different subnet'}"
            logging.info(f"IP info: {details} ")

        record_test_step(TCID, "IP subnet & MAC check", "PASS" if passed else "FAIL", details)
        step_results.append(("IP subnet & MAC check", "PASS" if passed else "FAIL", details))

        img2 = dut._capture_screenshot(logdir, "step2_ip_mac")
        if img2 and img2.exists():
            allure.attach.file(str(img2), name="Screenshot - IP/MAC", attachment_type=allure.attachment_type.PNG)

        if not passed:
            all_steps_passed = False

        original_mac = mac_addr

    # --- Step 3: Reboot device ---
    with allure.step("Reboot device"):
        success, boot_debug = dut.wait_for_device_boot(serial, timeout=150)
        passed = success is True
        details = "Reboot command sent" if passed else "Failed to send reboot command"
        record_test_step(TCID, "Device reboot", "PASS" if passed else "FAIL", details)
        step_results.append(("Device reboot", "PASS" if passed else "FAIL", details))

        if not passed:
            all_steps_passed = False

        # 等待设备重启完成（可根据实际调整）
        time.sleep(30)

    # --- Step 4: Wait for Wi-Fi reconnect and get MAC again ---
    # --- Step 4: Wait for Wi-Fi reconnect and get MAC again ---
    with allure.step("Wait for Wi-Fi reconnect and get MAC after reboot"):
        max_wait = 90
        ssid_after = None
        for i in range(max_wait // 5):
            ssid_after = dut.get_connected_ssid_adb(serial)
            if ssid_after == target_ssid:
                logging.info(f"Reconnected to {target_ssid} after reboot.")
                break
            time.sleep(5)
        else:
            # 进入 else 表示循环结束仍未连接
            error_msg = f"Failed to reconnect to '{target_ssid}' after reboot. Current SSID: '{ssid_after}'"
            logging.error(error_msg)
            record_test_step(TCID, "Wi-Fi reconnection after reboot", "FAIL", error_msg)
            pytest.fail(error_msg)  # ← 关键：立即失败！

        # 只有成功重连后，才检查 MAC
        mac_after = UiAutomationMixin.get_wifi_mac_adb(serial)
        if not mac_after:
            pytest.fail("Could not retrieve MAC address after reboot")

        passed = (mac_after == original_mac)
        details = f"Original MAC: {original_mac}, After reboot: {mac_after} → {'Match' if passed else 'Mismatch'}"
        logging.info(f"Step 4 Result: {details} ")
        record_test_step(TCID, "MAC persistence after reboot", "PASS" if passed else "FAIL", details)

        if not passed:
            pytest.fail("MAC address changed after reboot!")

    # Final assertion (optional)
    assert all_steps_passed, "One or more steps failed"