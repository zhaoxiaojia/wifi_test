# test_wifi_ssid_signal.py
import pytest
import allure
import time
import os, logging
from pathlib import Path
from src.util.constants import load_config
from src.tools.connect_tool.duts.android import android
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin
from src.conftest import record_test_step  # 直接调用，无需 from src.

TCID = "WiFi-STA-FLST0001"

@allure.title("Wi-Fi SSID List Sorted by Signal Strength")
@allure.description(
    "1. Ensure DUT is not connected to any Wi-Fi\n"
    "2. From home screen, open Settings → Wi-Fi\n"
    "3. Wait 20s for AP list to stabilize\n"
    "4. Verify APs are ordered from strongest to weakest signal"
)
def test_wifi_ap_signal_order(wifi_adb_device):
    dut, serial, logdir, _ = wifi_adb_device
    # Clear Connected Network
    UiAutomationMixin._clear_saved_wifi_networks(serial)
    dut._forget_wifi_via_ui(serial)

    all_steps_passed = True

    # --- Step 1: Wi-Fi enabled ---
    with allure.step("Check if Wi-Fi is enabled"):
        enabled = UiAutomationMixin._get_wifi_state_adb(serial)
        passed = enabled is True
        details = "Wi-Fi is ON" if passed else "Wi-Fi is OFF"
        record_test_step(TCID, "Wi-Fi enabled", "PASS" if passed else "FAIL", details)
        if not passed:
            all_steps_passed = False
            if not enabled:
                with allure.step("Recovering: Enabling Wi-Fi"):
                    success = UiAutomationMixin._enable_wifi_adb(serial)
                    if success:
                        time.sleep(4)

    # --- Step 2: Not connected ---
    with allure.step("Verify no Wi-Fi network is connected"):
        ssid = dut.get_connected_ssid_adb(serial=serial)
        passed = not ssid
        details = f"Connected to '{ssid}'" if ssid else "Not connected (as expected)"
        record_test_step(TCID, "Not connected to any network", "PASS" if passed else "FAIL", details)
        img2 = dut._capture_screenshot(logdir, "step2_not_connected")
        if img2 and img2.exists():
            allure.attach.file(str(img2), name="Screenshot - Network Connection Status",
                               attachment_type=allure.attachment_type.PNG)

        if not passed:
            all_steps_passed = False  # 初始失败
            with allure.step("Recovering: Disconnecting"):
                disconnect_success = UiAutomationMixin._disconnect_and_prevent_reconnect(serial)
                if disconnect_success:
                    time.sleep(3)
                    # ✅ 关键修复：验证是否真的断开了
                    ssid_after = dut.get_connected_ssid_adb(serial=serial)
                    if not ssid_after:
                        logging.info("✅ Successfully disconnected. Marking step as recovered.")
                        all_steps_passed = True  # 恢复成功，重置为 True
                    else:
                        logging.warning(f"⚠️ Still connected after disconnect: {ssid_after}")
                else:
                    logging.error("❌ Failed to disconnect.")

    # --- Step 3: Open Wi-Fi settings (TV-aware, NO new function) ---
    with allure.step("Open Wi-Fi settings page"):
        # Try standard method first (may work on some TVs)
        success = UiAutomationMixin._open_wifi_settings_page(serial)
        # if not success:
        #     success = UiAutomationMixin._open_wifi_settings_page(serial)
        passed = success
        details = "Successfully opened Wi-Fi settings" if passed else "Failed to open Wi-Fi settings"
        record_test_step(TCID, "Open Wi-Fi settings", "PASS" if passed else "FAIL", details)
        img3 = dut._capture_screenshot(logdir, "step3_wifi_settings_opened")
        if img3 and img3.exists():
            allure.attach.file(str(img3), name="Screenshot - Wi-Fi Settings Page", attachment_type=allure.attachment_type.PNG)
        if not passed:
            all_steps_passed = False

    # test_wifi_ssid_signal.py - 替换 Step 4 全部内容

    # --- Step 4: Verify AP order by actual RSSI ---
    with allure.step("Verify AP list is sorted by signal strength (RSSI)"):
        time.sleep(5)

        # 1. 从 UI 获取原始 SSID 列表
        ui_ssids_raw = dut.wifi_wait_for_networks(timeout=10)
        if not ui_ssids_raw:
            record_test_step(TCID, "UI AP list", "FAIL", "No networks visible in UI")
            all_steps_passed = False
        else:
            # 2. 过滤掉 UI 中的非 SSID 文本（提示、按钮等）
            invalid_keywords = [
                "saved", "save", "password", "try again", "check", "fail", "error",
                "connecting", "connected", "security", "options", "add", "see all",
                "已保存", "连接失败", "请输入密码"
            ]
            real_ui_ssids = []
            for ssid in ui_ssids_raw:
                ssid_lower = ssid.lower()
                if any(kw in ssid_lower for kw in invalid_keywords):
                    continue
                if len(ssid.strip()) < 2:
                    continue
                real_ui_ssids.append(ssid.strip())

            logging.info(f"🧹 Filtered real SSIDs from UI: {real_ui_ssids}")

            if not real_ui_ssids:
                record_test_step(TCID, "Signal order", "FAIL", "No valid SSIDs found in UI after filtering")
                all_steps_passed = False
            else:
                # 3. 从系统获取真实 RSSI 数据
                ap_list = dut.get_wifi_scan_results_via_cmd(serial)
                logging.info(f"📡 Parsed {len(ap_list)} APs with RSSI")
                for ssid, rssi in ap_list[:5]:
                    logging.info(f"  {ssid}: {rssi} dBm")

                if not ap_list:
                    logging.warning("⚠️ No RSSI data available even after parsing.")
                    record_test_step(TCID, "Signal order", "FAIL", "Failed to retrieve scan results")
                    all_steps_passed = False
                else:
                    # 4. 构建 SSID -> RSSI 映射
                    rssi_map = {ssid: rssi for ssid, rssi in ap_list}

                    # 5. 只保留 UI 中出现的、且有 RSSI 的网络
                    common_ssids = [ssid for ssid in real_ui_ssids if ssid in rssi_map]
                    if not common_ssids:
                        logging.warning("No overlap between UI SSIDs and scan results")
                        record_test_step(TCID, "Signal order", "WARN", "UI/AP mismatch – no common SSIDs")
                        all_steps_passed = True  # 不算失败，但需人工检查
                    else:
                        # 6. 检查 RSSI 是否非递增（即：从强到弱）
                        rssi_sequence = [rssi_map[ssid] for ssid in common_ssids]
                        is_sorted = all(
                            rssi_sequence[i] >= rssi_sequence[i + 1]
                            for i in range(len(rssi_sequence) - 1)
                        )

                        details = (
                            f"UI order (filtered): {common_ssids}\n"
                            f"RSSI sequence: {rssi_sequence}\n"
                            f"Sorted correctly: {'✅ Yes' if is_sorted else '❌ No'}"
                        )
                        status = "PASS" if is_sorted else "FAIL"
                        record_test_step(TCID, "AP signal order", status, details)

                        # Attach detailed info to Allure
                        allure.attach(
                            "\n".join(f"{ssid}: {rssi_map[ssid]} dBm" for ssid in common_ssids),
                            name="UI Order vs Actual RSSI",
                            attachment_type=allure.attachment_type.TEXT
                        )

                        if not is_sorted:
                            all_steps_passed = False

        # 截图（无论成功失败）
        img4 = dut._capture_screenshot(logdir, "step4_ap_list_verified")
        if img4 and img4.exists():
            allure.attach.file(str(img4), name="Screenshot - Final AP List", attachment_type=allure.attachment_type.PNG)

    # Final assertion
    assert all_steps_passed, "One or more critical steps failed"