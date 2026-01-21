from __future__ import annotations
import logging, subprocess
import time,re,os
from typing import List, Optional, Set
from pathlib import Path
from typing import Tuple

class UiAutomationMixin:
    def u(self, type="u2"):
        return self._u_impl(type=type)

    def _u_impl(self, *, type="u2"):
        raise NotImplementedError

    def uiautomator_dump(self, filepath="", uiautomator_type="u2"):
        return self._uiautomator_dump_impl(filepath=filepath, uiautomator_type=uiautomator_type)

    def _uiautomator_dump_impl(self, *, filepath="", uiautomator_type="u2"):
        raise NotImplementedError

    # ==============================
    # 🔌 Wi-Fi UI Helper Methods (Mixin)
    # ==============================

    def wifi_is_valid_ssid(self, text: str) -> bool:
        """判断文本是否可能是有效的 SSID"""
        clean = text.strip()
        if not clean or len(clean) > 32 or len(clean) < 1:
            return False
        lower_clean = clean.lower()
        # 非SSID关键词集合
        non_ssid_keywords: Set[str] = {
            'see all', 'add network', 'saved networks', 'connected', 'wlan', 'wi-fi',
            'network & internet', 'other options', 'scanning always available', 'settings',
            'hotspot', 'internet', 'preferences', 'more', 'turn on wi-fi', 'off', 'on',
            'toggle', 'scan', 'search', 'available networks', 'no networks found',
            'airplane mode', 'connected', '已连接', 'no sim', 'calls & sms', 'data saver',
            'scanning...', 'quick connect', 'add new network', 'options', 'share'
        }
        if lower_clean in non_ssid_keywords:
            return False
        if clean.isdigit():
            return False
        if any(c in clean for c in ['\n', '\t', ':', '—', '–', '...', '…', '"', "'", '（', '）']):
            return False
        return True

    @staticmethod
    def _open_wifi_settings_page(serial: str) -> bool:
        """
        Open Android Wi-Fi Settings page via ADB.

        Args:
            serial (str): Device serial number.

        Returns:
            bool: True if command executed successfully, False otherwise.
        """
        try:
            cmd = f"adb -s {serial} shell am start -a android.settings.WIFI_SETTINGS"
            logging.debug(f"Executing: {cmd}")
            ret = os.system(cmd)
            # os.system returns 0 on success
            if ret == 0:
                logging.info(f"Successfully opened Wi-Fi settings page on {serial}")
                return True
            else:
                logging.error(f"Failed to open Wi-Fi settings page on {serial}, exit code: {ret}")
                return False
        except Exception as e:
            logging.exception(f"Exception while opening Wi-Fi settings on {serial}: {e}")
            return False

    def wifi_wait_for_networks(self, timeout: int = 12) -> List[str]:
        """
        Wait for real Wi-Fi SSIDs to appear on screen.
        Returns list of detected SSIDs.
        """
        ui_tool = self.u(type="u2")
        start_time = time.time()
        scan_clicked = False

        while time.time() - start_time < timeout:
            try:
                all_texts = self._get_visible_texts(ui_tool)
                candidates = [text for text in all_texts if self.wifi_is_valid_ssid(text)]

                if candidates:
                    logging.info(f"✅ Found real SSIDs: {candidates}")
                    return candidates

                # 5秒后尝试点击 Scan / 搜索
                if not scan_clicked and time.time() - start_time > 5:
                    if ui_tool.wait(text="Scan", timeout=1):
                        logging.info("Triggered manual 'Scan' to refresh networks.")
                        scan_clicked = True
                        time.sleep(2)
                    elif ui_tool.wait(text="搜索", timeout=1):
                        logging.info("Triggered manual '搜索' to refresh networks.")
                        scan_clicked = True
                        time.sleep(2)

                time.sleep(1)
            except Exception as e:
                logging.warning(f"Error during Wi-Fi scan wait: {e}")
                time.sleep(1)

        logging.warning("⚠️ Timeout waiting for real Wi-Fi networks (SSIDs).")
        return []

    def wifi_check_connection_status(self) -> bool:
        """Check if device is currently connected to a Wi-Fi network via UI."""
        ui_tool = self.u(type="u2")
        visible_texts = [t.lower() for t in self._get_visible_texts(ui_tool)]
        return "connected" in visible_texts or "已连接" in visible_texts

    staticmethod

    @staticmethod
    def wifi_is_on_settings_page(ui_tool) -> bool:
        """
        Check if the current UI screen is the Wi-Fi settings page.

        :param ui_tool: An instance of UiautomatorTool (e.g., from dut.u())
        :return: True if on Wi-Fi settings page, False otherwise.
        """
        try:
            # Look for key indicators of Wi-Fi settings page
            if (ui_tool.wait(text="Wi-Fi", timeout=2) or
                    ui_tool.wait(text="WLAN", timeout=2) or
                    ui_tool.wait(text="无线局域网", timeout=2) or
                    ui_tool.xpath('//*[@resource-id="com.android.settings:id/wifi_settings"]').exists):
                return True
        except Exception as e:
            logging.debug(f"Error in wifi_is_on_settings_page: {e}")
        return False

    # ------------------------------
    # 🔧 Private helper (shared)
    # ------------------------------

    def _get_visible_texts(self, ui_tool) -> List[str]:
        """Safely extract all non-empty TextView texts from current UI."""
        texts = set()
        try:
            for view in ui_tool.d2(className="android.widget.TextView"):
                text = view.info.get("text", "")
                if isinstance(text, str) and text.strip():
                    texts.add(text.strip())
        except Exception as e:
            logging.debug(f"Failed to extract visible texts: {e}")
        return list(texts)

    def _get_wifi_state_adb(serial: str) -> bool:
        """Use ADB to check if Wi-Fi is enabled (returns True if ON)."""
        try:
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "dumpsys wifi"],
                capture_output=True, text=True, timeout=5, encoding='utf-8', errors='ignore'
            )
            output = result.stdout

            # ✅ 关键修复：确保 output 是字符串
            if not output or not isinstance(output, str):
                logging.warning("ADB dumpsys wifi returned empty or non-string output")
                return False

            if "mWifiEnabled=true" in output:
                return True
            if "mWifiEnabled=false" in output:
                return False
            if "Wi-Fi is enabled" in output:
                return True
            if "Wi-Fi is disabled" in output:
                return False

            logging.warning(f"Could not determine Wi-Fi state from dumpsys. First 200 chars: {output[:200]}")
            return False  # 安全默认：假设关闭

        except Exception as e:
            logging.warning(f"Failed to get Wi-Fi state via ADB: {e}")
            return False

    def wifi_get_connected_ssid(self) -> str:
        """
        Try to extract the SSID of the currently connected Wi-Fi network.
        Returns empty string if not connected.
        """
        ui_tool = self.u(type="u2")
        time.sleep(2)
        try:
            # Look for 'Connected' or '已连接' element
            connected_elements = ui_tool.d2.xpath('//*[@text="Connected" or @text="已连接"]')
            if connected_elements.exists:
                parent = connected_elements.parent()
                if parent.exists:
                    ssid_text = parent.child(className="android.widget.TextView").get_text()
                    if ssid_text and ssid_text not in ["Connected", "已连接"]:
                        logging.info(f"Detected connected SSID via UI: {ssid_text}")
                        return ssid_text
        except Exception as e:
            logging.debug(f"XPath failed in wifi_get_connected_ssid: {e}")
        logging.info("No 'Connected' indicator found. Assuming not connected.")
        return ""

    def get_connected_ssid_adb(self, serial: Optional[str] = None) -> str:
        device_serial = serial or getattr(self, 'serial', None)
        if not device_serial:
            return ""

        try:
            result = subprocess.run(
                ["adb", "-s", device_serial, "shell", "dumpsys wifi"],
                capture_output=True, text=True, timeout=8,
                encoding='utf-8', errors='ignore'
            )
            output = result.stdout
            if not output:
                return ""

            # === 关键：先检查当前状态是否为“已连接” ===
            # 常见的“已连接”状态关键词（不同 Android 版本略有差异）
            is_in_connected_state = any(state in output for state in [
                "curState=ConnectedState",
                "curState=ObtainingIpState",
                "curState=RoamingState"
                "curState=L2ConnectedState",  # Android 10+
                "curState=L3ConnectedState",  # L3 Network
                "curState=StartedState"
            ])

            if not is_in_connected_state:
                return ""

            # === 新增：二次验证 wlan0 是否有 IP ===
            try:
                ip_result = subprocess.run(
                    ["adb", "-s", device_serial, "shell", "ip addr show wlan0"],
                    capture_output=True, text=True, timeout=5
                )
                # 如果没有 inet 行，说明没 IP
                if "inet " not in ip_result.stdout:
                    logging.debug("No IP on wlan0, treating as disconnected despite state.")
                    return ""
            except:
                pass  # fallback to dumpsys only

            # 如果不在连接状态，直接返回空（不管 mLastNetworkSsid 是什么）
            if not is_in_connected_state:
                logging.debug("Device is not in a connected Wi-Fi state.")
                return ""

            # === 只有在连接状态下，才尝试提取 SSID ===
            ssid_match = re.search(r'mLastNetworkSsid\s*=\s*"([^"]*)"', output)
            if ssid_match:
                ssid = ssid_match.group(1).strip()
                if ssid and ssid not in ("", "<unknown ssid>"):
                    return ssid

            ssid_match2 = re.search(r'SSID:\s*"([^"]+)"', output)
            if ssid_match2:
                candidate = ssid_match2.group(1).strip()
                if self.wifi_is_valid_ssid(candidate):
                    return candidate

            # 在连接状态但没拿到 SSID？可能是隐藏网络
            return "CONNECTED_HIDDEN_SSID"

        except Exception as e:
            logging.error(f"Error in get_connected_ssid_adb: {e}")
            return ""

    # ui_mixin.py - inside UiAutomationMixin class
    def enter_wifi_network_list_page(self, timeout: int = 5) -> bool:
        """
        Click on 'Wi-Fi' / 'WLAN' entry to enter the actual network scan list page.
        Returns True if clicked successfully.
        """
        ui_tool = self.u()
        for keyword in ["Wi-Fi", "WLAN", "无线局域网"]:
            if ui_tool.wait(text=keyword, timeout=timeout):
                logging.info(f"Clicked '{keyword}' to enter Wi-Fi network list.")
                time.sleep(2)
                return True
        logging.warning("Failed to enter Wi-Fi network list page.")
        return False

    def _capture_screenshot(dut, logdir: Path, step_name: str):
        """Capture and return path to screenshot."""
        safe_name = "".join(c if c.isalnum() else "_" for c in step_name)
        timestamp = int(time.time())
        img_path = logdir / f"{safe_name}_{timestamp}.png"
        try:
            dut.u().screenshot(str(img_path))
            return img_path
        except Exception as e:
            print(f"Failed to capture screenshot for '{step_name}': {e}")
            return None

    def is_wired_connection_active(self, serial: str, timeout: int = 8) -> Tuple[bool, str]:
        """
        Check if any wired (Ethernet) interface is active.
        Returns:
            (is_active: bool, debug_output: str)
        """
        wired_ifaces = ["eth0", "enp0s1", "wired0"]
        active_wired = []
        output_log = ""

        for iface in wired_ifaces:
            try:
                # Run: adb -s <serial> shell ip addr show <iface>
                result = subprocess.run(
                    ["adb", "-s", serial, "shell", "ip addr show", iface],
                    capture_output=True, text=True, timeout=8
                )
                output = result.stdout.strip()
                output_log += f"\n[iface: {iface}]\n{output}"
                if "state UP" in output or "inet " in output:
                    active_wired.append(iface)
            except Exception as e:
                output_log += f"\n[iface: {iface} EXCEPTION] {e}"

        is_active = len(active_wired) > 0
        summary = f"Wired interfaces active: {active_wired}" if is_active else "No active wired interfaces"
        full_output = f"{summary}\n--- Details ---{output_log}"
        return is_active, full_output

    def wait_for_device_boot(self, serial: str, timeout: int = 150) -> Tuple[bool, str]:
        """
        Wait for device to come online and complete boot.
        Returns:
            (booted: bool, debug_info: str)
        """
        debug_log = []

        # Step 1: Wait for ADB device to appear
        # ===== 阶段 1: 发起 reboot (只做一次!) =====
        try:
            # 先检查设备是否在线
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            if serial in result.stdout:
                # 设备在线，才发送 reboot
                subprocess.run(["adb", "-s", serial, "reboot"], check=True, timeout=20)
                logging.info("Reboot command sent successfully.")
            else:
                logging.warning("Device not online. Assuming reboot is already in progress.")
        except Exception as e:
            logging.error(f"Warning: Failed to send reboot command: {e}. Proceeding to wait...")

        # 等待设备消失（避免立即检测到旧会话）
        time.sleep(5)

        start = time.time()
        while time.time() - start < timeout:
            try:
                subprocess.run(
                    ["adb", "-s", serial, "wait-for-device"],
                    check=True, timeout=timeout
                )
                logging.info("Device detected via ADB")
                break
            except subprocess.TimeoutExpired:
                continue
            except Exception as e:
                time.sleep(2)
                continue
        else:
            logging.error("Timeout: Device did not come back online.")
            return False, "\n".join(debug_log)

        # Step 2: Wait for sys.boot_completed == 1
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(
                    ["adb", "-s", serial, "shell", "getprop", "sys.boot_completed"],
                    capture_output=True, text=True, timeout=10
                )
                if result.stdout.strip() == "1":
                    logging.info("Boot completed (sys.boot_completed=1)")
                    return True, "\n".join(debug_log)
            except Exception as e:
                logging.warning(f"getprop error: {e}")
            time.sleep(2)

        msg = f"Boot completion not detected within {timeout}s"
        logging.error(msg)
        return False, "\n".join(debug_log)

    # ui_mixin.py - inside UiAutomationMixin class

    @staticmethod
    def _enable_wifi_adb(serial: str, timeout: int = 10) -> bool:
        """
        Enable Wi-Fi via ADB command 'svc wifi enable'.
        Returns True if command executed successfully (does not guarantee Wi-Fi is fully up).
        """
        try:
            import subprocess
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "svc", "wifi", "enable"],
                capture_output=True, text=True, timeout=timeout
            )
            if result.returncode == 0:
                logging.info(f"Wi-Fi enable command sent successfully to {serial}")
                return True
            else:
                logging.error(f"Failed to enable Wi-Fi on {serial}: {result.stderr}")
                return False
        except Exception as e:
            logging.error(f"Exception while enabling Wi-Fi on {serial}: {e}")
            return False

    @staticmethod
    def _disable_wifi_adb(serial: str, timeout: int = 10) -> bool:
        """
        Enable Wi-Fi via ADB command 'svc wifi enable'.
        Returns True if command executed successfully (does not guarantee Wi-Fi is fully up).
        """
        try:
            import subprocess
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "svc", "wifi", "disable"],
                capture_output=True, text=True, timeout=timeout
            )
            if result.returncode == 0:
                logging.info(f"Wi-Fi disable command sent successfully to {serial}")
                return True
            else:
                logging.error(f"Failed to disable Wi-Fi on {serial}: {result.stderr}")
                return False
        except Exception as e:
            logging.error(f"Exception while disabling Wi-Fi on {serial}: {e}")
            return False

    @staticmethod
    def _disconnect_and_prevent_reconnect(serial: str, timeout: int = 10) -> bool:
        """
        Disconnect from current Wi-Fi and prevent auto-reconnect by removing the network.
        This ensures device stays disconnected for subsequent test steps.
        """
        try:
            import subprocess
            import time

            # Step 1: List networks to find CURRENT one
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "wpa_cli", "list_networks"],
                capture_output=True, text=True, timeout=timeout
            )

            if result.returncode != 0:
                logging.error(f"Failed to list Wi-Fi networks on {serial}")
                return False

            lines = result.stdout.strip().split('\n')
            current_net_id = None
            for line in lines[1:]:  # Skip header
                if "[CURRENT]" in line:
                    parts = line.split()
                    if parts:
                        current_net_id = parts[0]
                        break

            if current_net_id is None:
                logging.info("No current network found, already disconnected.")
                return True

            # Step 2: Remove (forget) the current network
            result2 = subprocess.run(
                ["adb", "-s", serial, "shell", "wpa_cli", "remove_network", current_net_id],
                capture_output=True, text=True, timeout=timeout
            )

            if result2.returncode == 0:
                logging.info(f"Removed network ID {current_net_id} on {serial} to prevent reconnect")
                time.sleep(2)
                return True
            else:
                logging.error(f"Failed to remove network {current_net_id}: {result2.stderr}")
                return False

        except Exception as e:
            logging.error(f"Exception in _disconnect_and_prevent_reconnect on {serial}: {e}")
            return False