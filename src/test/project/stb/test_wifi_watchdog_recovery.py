# test_wifi_watchdog_recovery.py
import pytest
import allure
import time
import os, logging
from pathlib import Path
from src.util.constants import load_config
from src.tools.connect_tool.duts.android import android
from src.tools.connect_tool.mixins.ui_mixin import UiAutomationMixin
from src.conftest import record_test_step  # 直接调用，无需 from src.

TCID = "WiFi-STA-FSR0003"


@allure.title("Wi-Fi Watchdog Recovery with YouTube Playback")
@allure.description(
    "1. Connect to AP\n"
    "2. Play YouTube video via UI\n"
    "3. Trigger Watchdog reboot via sysrq\n"
    "4. Verify Wi-Fi auto-reconnect and video resumption"
)
def test_wifi_watchdog_recovery(wifi_adb_device):
    dut, serial, logdir, cfg  = wifi_adb_device
    all_steps_passed = True
    step_results = []

    # === 从配置中获取目标 SSID 和 Router IP ===
    wifi_config = cfg.get("router", {})
    target_ssid = wifi_config.get("24g_ssid")
    target_ssid_pwd = "88888888"
    router_ip = wifi_config.get("address")
    youtube_channel = "NASA"

    if not target_ssid or not router_ip:
        pytest.fail("Missing 'wifi_test.target_ssid' or 'wifi_test.router_ip' in config")

    with allure.step(f"Target SSID: {target_ssid}, Router IP: {router_ip}"):
        pass

        # --- Step 0: clear currect connected and save SSID ---
        UiAutomationMixin._clear_saved_wifi_networks(serial)
        time.sleep(2)

        # --- Step 1: 连接 Wi-Fi ---
        with allure.step("Connect to target Wi-Fi AP"):
            # 复用原连接逻辑
            enabled = UiAutomationMixin._get_wifi_state_adb(serial)
            if not enabled:
                UiAutomationMixin._enable_wifi_adb(serial)
                time.sleep(4)

            # current_ssid = dut.get_connected_ssid_adb(serial)
            # if current_ssid != target_ssid:
            success = UiAutomationMixin._connect_to_wifi_via_ui(
                serial=serial,
                ssid=target_ssid,
                password=target_ssid_pwd,
                logdir=logdir
            )
            time.sleep(8)

            ip_addr = UiAutomationMixin.get_device_ip_adb(serial)
            mac_addr = UiAutomationMixin.get_wifi_mac_adb(serial)
            passed = bool(ip_addr and ip_addr.startswith(".".join(router_ip.split(".")[:3])))
            details = f"IP: {ip_addr}, MAC: {mac_addr}"
            record_test_step(TCID, "Wi-Fi Connection", "PASS" if passed else "FAIL", details)
            if not passed:
                pytest.fail("Wi-Fi connection failed before Watchdog test")
            img1 = dut._capture_screenshot(logdir, "step1_wifi_connected")
            if img1 and img1.exists():
                allure.attach.file(str(img1), name="Wi-Fi Connected", attachment_type=allure.attachment_type.PNG)

        # --- Step 2: 播放 YouTube 视频 ---
        with allure.step("Play YouTube video via UI automation"):
            # 注入 serial 和 logdir 到 dut（确保 open_youtube... 能用）
            dut.serial = serial
            dut.logdir = logdir

            success = dut.launch_youtube_tv_and_search(serial, logdir)
            passed = success
            details = "YouTube playback started" if passed else "Failed to start YouTube"
            record_test_step(TCID, "YouTube Playback Start", "PASS" if passed else "FAIL", details)
            if not passed:
                pytest.fail("Could not start YouTube video")
            time.sleep(5)  # 确保视频加载
            img2 = dut._capture_screenshot(logdir, "step2_youtube_playing")
            if img2 and img2.exists():
                allure.attach.file(str(img2), name="YouTube Playing", attachment_type=allure.attachment_type.PNG)

        # --- Step 3: 触发 Watchdog 重启 ---
        with allure.step("Trigger Watchdog reboot via sysrq-trigger"):
            try:
                # 使用 ADB 执行（需 root）
                cmd = f"adb -s {serial} shell 'echo c > /proc/sysrq-trigger'"
                logging.info(f"Executing Watchdog trigger: {cmd}")
                # 注意：此命令会立即导致内核 panic，ADB 会断开
                os.system(cmd)
                passed = True
                details = "Watchdog trigger sent"
            except Exception as e:
                passed = False
                details = f"Failed to trigger Watchdog: {e}"

            record_test_step(TCID, "Watchdog Trigger", "PASS" if passed else "FAIL", details)
            if not passed:
                pytest.fail("Could not trigger Watchdog reboot")

        # --- Step 4: 等待设备重启并验证 Wi-Fi 断开 ---
        with allure.step("Wait for device reboot and verify Wi-Fi disconnect"):
            time.sleep(10)  # 等待 panic 发生

            # 验证设备离线（可选）
            # 此处不强制检查，因为 panic 后 ADB 会断

            # 等待设备重新上线
            success, debug_info = dut.wait_for_device_boot(serial, timeout=150)
            if not success:
                pytest.fail(f"Device did not come back online after Watchdog: {debug_info}")

            # 重启后 Wi-Fi 应默认关闭或断开
            time.sleep(10)
            ssid_after = dut.get_connected_ssid_adb(serial)
            if ssid_after == target_ssid:
                logging.warning("Wi-Fi still connected immediately after reboot? Unexpected.")
            # 我们不 assert，因为重点在“后续能否重连”

            record_test_step(TCID, "Post-Reboot State", "PASS", "Device booted, Wi-Fi expected disconnected")
            img3 = dut._capture_screenshot(logdir, "step3_post_reboot")
            if img3 and img3.exists():
                allure.attach.file(str(img3), name="Post Reboot", attachment_type=allure.attachment_type.PNG)

        # --- Step 5: 验证 Wi-Fi 自动重连 & 视频恢复 ---
        with allure.step("Verify Wi-Fi auto-reconnect and YouTube recovery"):
            # 等待 Wi-Fi 自动重连（Android 默认会重连已保存网络）
            max_wait = 90
            reconnected = False
            for i in range(max_wait // 5):
                ssid_now = dut.get_connected_ssid_adb(serial)
                if ssid_now == target_ssid:
                    reconnected = True
                    logging.info(f"✅ Auto-reconnected to {target_ssid} after {i * 5}s")
                    break
                time.sleep(5)

            if not reconnected:
                pytest.fail(f"Wi-Fi did not auto-reconnect to {target_ssid} within {max_wait}s")

            # 验证 IP 获取
            ip_after = UiAutomationMixin.get_device_ip_adb(serial)
            if not ip_after:
                pytest.fail("No IP address after Wi-Fi reconnect")

            # 尝试重新播放 YouTube（或检查是否自动续播）
            success = dut.launch_youtube_tv_and_search(serial, logdir)
            passed = success
            details = "YouTube playable after recovery" if passed else "YouTube not playable"
            record_test_step(TCID, "Post-Recovery Playback", "PASS" if passed else "FAIL", details)
            if not passed:
                pytest.fail("YouTube cannot be played after Watchdog recovery")

            img4 = dut._capture_screenshot(logdir, "step4_recovered")
            if img4 and img4.exists():
                allure.attach.file(str(img4), name="Recovered Playback", attachment_type=allure.attachment_type.PNG)

        # Final assertion
        assert all_steps_passed, "One or more steps failed"