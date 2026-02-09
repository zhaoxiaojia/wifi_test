from __future__ import annotations
import logging, subprocess
import time,re,os, tempfile,time
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Optional, List, Tuple, Any, Set

class UiAutomationMixin:
    def u(self, type="u2"):
        return self._u_impl(type=type)

    def _u_impl(self, *, type="u2"):
        raise NotImplementedError

    def uiautomator_dump(self, filepath="", uiautomator_type="u2"):
        return self._uiautomator_dump_impl(filepath=filepath, uiautomator_type=uiautomator_type)

    def _uiautomator_dump_impl(self, *, filepath="", uiautomator_type="u2"):
        raise NotImplementedError

    def wifi_is_valid_ssid(self, text: str) -> bool:
        """Check valid SSID"""
        clean = text.strip()
        if not clean or len(clean) > 32 or len(clean) < 1:
            return False
        lower_clean = clean.lower()
        # invalid SSID list
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
    def is_wifi_network_saved(serial: str, ssid: str, timeout: int = 10) -> bool:
        """
        Check if a Wi-Fi network (by SSID) is in 'Saved' state on the device.

        This function queries the system's Wi-Fi configuration via 'dumpsys wifi'
        and checks for the presence of the SSID in the output, which indicates that
        the network credentials are stored, regardless of its current connection or
        enabled/disabled status.

        Args:
            serial (str): The ADB serial number of the target device.
            ssid (str): The SSID of the Wi-Fi network to check.
            timeout (int): Timeout for the ADB command execution in seconds.

        Returns:
            bool: True if the network is saved, False otherwise.
        """
        # Construct the precise grep command based on observed dumpsys format
        # Note: The format in dumpsys uses 'SSID: "..."', not 'SSID="..."'.
        escaped_ssid = ssid.replace('"', '\\"')  # Escape quotes in SSID if any
        cmd = f"adb -s {serial} shell \"dumpsys wifi | grep 'SSID: \\\"{escaped_ssid}\\\"'\""

        logging.debug(f"Checking if SSID '{ssid}' is saved with command: {cmd}")

        try:
            output = UiAutomationMixin._run_adb_capture_output(cmd, timeout=timeout)
            # If the grep finds a match, stdout will contain the line; otherwise, it's empty.
            is_saved = len(output.strip()) > 0
            logging.info(f"SSID '{ssid}' is {'Saved' if is_saved else 'NOT Saved'} on {serial}.")
            return is_saved
        except Exception as e:
            logging.error(f"Exception while checking saved state for SSID '{ssid}': {e}")
            return False

    @staticmethod
    def _go_to_home(serial: str, timeout: int = 5) -> bool:
        """
        Return to device home screen (Launcher) via ADB Intent.

        This is more reliable than KEYCODE_HOME on vendor-customized ROMs.

        Args:
            serial (str): Device serial number.
            timeout (int): Command timeout in seconds.

        Returns:
            bool: True if command executed successfully, False otherwise.
        """
        try:
            cmd = [
                "adb", "-s", serial, "shell",
                "am", "start",
                "-a", "android.intent.action.MAIN",
                "-c", "android.intent.category.HOME"
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='ignore'
            )
            if result.returncode == 0:
                logging.info(f"✅ Successfully returned to home screen on {serial}")
                return True
            else:
                logging.error(f"❌ Failed to go home on {serial}: {result.stderr.strip()}")
                return False
        except subprocess.TimeoutExpired:
            logging.error(f"⏰ Timeout while trying to go home on {serial}")
            return False
        except Exception as e:
            logging.exception(f"💥 Exception in _go_to_home on {serial}: {e}")
            return False

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
            success = UiAutomationMixin._go_to_home(serial)

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

    @staticmethod
    def get_device_ip_adb(serial: str) -> str:
        """
        Get the first valid Wi-Fi IP address from any active interface.
        Skips loopback (127.*) and link-local (169.254.*) addresses.
        Prioritizes interfaces starting with 'wlan'.
        """
        try:
            # Get all interface address
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "ip addr show"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=8
            )
            lines = result.stdout.splitlines()

            # IP List
            candidates = []  # [(interface, ip), ...]

            current_iface = None
            for line in lines:
                # eg "3: wlan0: <BROADCAST,MULTICAST,UP> ..."
                if line.strip() and line[0].isdigit():
                    parts = line.split(':')
                    if len(parts) >= 2:
                        current_iface = parts[1].strip()
                elif "inet " in line and current_iface:
                    ip_with_mask = line.strip().split()[1]
                    ip = ip_with_mask.split("/")[0]
                    if ip.startswith("127.") or ip.startswith("169.254."):
                        continue
                    candidates.append((current_iface, ip))

            # Return wlan* IP
            for iface, ip in candidates:
                if iface and iface.startswith("wlan"):
                    logging.debug(f"Found valid IP on {iface}: {ip}")
                    return ip

            # If no wlan，return vaild IP（fallback）
            if candidates:
                iface, ip = candidates[0]
                logging.warning(f"No 'wlan' interface found. Using IP from {iface}: {ip}")
                return ip

        except Exception as e:
            logging.error(f"Failed to get IP via ADB: {e}")

        return ""

    @staticmethod
    def get_wifi_mac_adb(serial: str) -> str:
        """
        Get Wi-Fi MAC address from any active wlan interface.
        Returns uppercase, colon-separated format (e.g., AA:BB:CC:DD:EE:FF).
        """
        try:
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "ip addr show"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=5
            )
            lines = result.stdout.splitlines()
            current_iface = None

            for line in lines:
                if line.strip() and line[0].isdigit():
                    parts = line.split(':')
                    if len(parts) >= 2:
                        current_iface = parts[1].strip()
                elif "link/ether" in line and current_iface and current_iface.startswith("wlan"):
                    mac = line.strip().split()[1].upper()
                    # Validate MAC format
                    if len(mac.replace(":", "")) == 12:
                        return mac
        except Exception as e:
            logging.error(f"Failed to get Wi-Fi MAC: {e}")
        return ""

    def _get_wifi_state_adb(serial: str) -> bool:
        """Use ADB to check if Wi-Fi is enabled (returns True if ON)."""
        try:
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "dumpsys wifi"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=5, encoding='utf-8', errors='ignore'
            )
            output = result.stdout

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
            return False

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

    def get_connected_ssid_via_cli_adb(self, serial):
        """Reliable SSID fetch via 'iw dev wlan0 link' without shell pipes."""
        try:
            result = subprocess.run(
                ["adb", "-s", serial, "shell", "su 0 iw dev wlan0 link"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=8,
                encoding='utf-8',
                errors='ignore'
            )
            logging.info(f"wlan0 link result : {result}")
            if result.returncode != 0:
                logging.warning(f"Failed to run 'iw dev wlan0 link': {result.stderr}")
                return ""

            output = result.stdout
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("SSID:"):
                    ssid = line[5:].strip()  # Remove "SSID:"
                    if ssid:
                        return ssid
            return ""  # Not connected or hidden SSID
        except Exception as e:
            logging.error(f"Exception in get_connected_ssid_via_cli_adb: {e}")
            return ""

    def get_connected_ssid_adb(self, serial: Optional[str] = None) -> str:
        device_serial = serial or getattr(self, 'serial', None)
        if not device_serial:
            return ""

        try:
            result = subprocess.run(
                ["adb", "-s", device_serial, "shell", "dumpsys wifi"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=8,
                encoding='utf-8', errors='ignore'
            )
            output = result.stdout
            if not output:
                return ""

            # Usually Connected status
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

            # Verify if wlan0 has IP
            try:
                ip_result = subprocess.run(
                    ["adb", "-s", device_serial, "shell", "ip addr show wlan0"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=5
                )
                if "inet " not in ip_result.stdout:
                    logging.debug("No IP on wlan0, treating as disconnected despite state.")
                    return ""
            except:
                pass  # fallback to dumpsys only

            if not is_in_connected_state:
                logging.debug("Device is not in a connected Wi-Fi state.")
                return ""

            # Get SSID if valid
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

            return "CONNECTED_HIDDEN_SSID"

        except Exception as e:
            logging.error(f"Error in get_connected_ssid_adb: {e}")
            return ""

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
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=8
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
        try:
            result = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True)
            if serial in result.stdout:
                # reboot device
                subprocess.run(["adb", "-s", serial, "reboot"], check=True, timeout=20)
                logging.info("Reboot command sent successfully.")
            else:
                logging.warning("Device not online. Assuming reboot is already in progress.")
        except Exception as e:
            logging.error(f"Warning: Failed to send reboot command: {e}. Proceeding to wait...")

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
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=10
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
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=timeout
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
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=timeout
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
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=timeout
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
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=timeout
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

    @staticmethod
    def _run_adb(cmd: str) -> None:
        """执行 ADB 命令（静默）"""
        try:
            #subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,  # 自动处理 stdout/stderr
                text=True,  # 返回字符串而非 bytes
                timeout=30,
                # 防止句柄泄漏
                stdin=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                logging.error(f"ADB command failed: {result.stderr}")
            return result.stdout

        except subprocess.TimeoutExpired:
            logging.error("ADB command timed out")
            raise
        except Exception as e:
            logging.error(f"Exception running ADB: {e}")
            raise

    # 在 ui_mixin.py 中，UiAutomationMixin 类内添加：
    @staticmethod
    def _run_adb_capture_output(cmd: str, timeout: int = 10) -> str:
        """执行 ADB 命令并返回 stdout（用于需要解析输出的场景）"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='ignore'
            )
            if result.returncode == 0:
                return result.stdout
            else:
                logging.warning(f"ADB command failed (exit {result.returncode}): {cmd}")
                logging.debug(f"STDERR: {result.stderr}")
                return ""
        except subprocess.TimeoutExpired:
            logging.error(f"ADB command timed out: {cmd}")
            return ""
        except Exception as e:
            logging.error(f"Exception running ADB: {e}")
            return ""

    @staticmethod
    def _dump_ui(serial: str, logdir: Optional[Path] = None) -> Any:
        """Dump 当前 UI 并返回 XML 根节点。解析后自动清理临时文件（除非指定 logdir）"""
        remote_path = "/sdcard/window_dump.xml"
        if logdir is None:
            # 创建一个真正的临时文件（自动删除）
            with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.xml') as tmp:
                local_path = Path(tmp.name)
        else:
            local_path = logdir / f"ui_dump_{int(time.time())}.xml"

        try:
            # 执行 dump 和 pull
            UiAutomationMixin._run_adb(f"adb -s {serial} shell uiautomator dump {remote_path} --compressed")
            UiAutomationMixin._run_adb(f"adb -s {serial} pull {remote_path} {local_path}")

            # 关键：读取文件内容到内存，再解析
            with open(local_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            root = ET.fromstring(xml_content)

            logging.debug(f"[DEBUG] UI dumped and parsed from: {local_path}")
            return root

        except Exception as e:
            logging.error(f"Failed to dump or parse UI: {e}")
            raise

        finally:
            # 只有临时文件才删除（且确保已读入内存）
            if logdir is None and local_path.exists():
                local_path.unlink() # 忽略删除失败
    # def _dump_ui(serial: str, logdir: Optional[Path] = None) -> Any:
    #     """Dump 当前 UI 并返回 XML 根节点。解析后自动清理临时文件（除非指定 logdir）"""
    #     remote_path = "/sdcard/window_dump.xml"
    #     if logdir is None:
    #         # 创建一个真正的临时文件（自动删除）
    #         with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix='.xml') as tmp:
    #             local_path = Path(tmp.name)
    #     else:
    #         local_path = logdir / f"ui_dump_{int(time.time())}.xml"
    #
    #     try:
    #         # 执行 dump 和 pull
    #         UiAutomationMixin._run_adb(f"adb -s {serial} shell uiautomator dump {remote_path} --compressed")
    #         UiAutomationMixin._run_adb(f"adb -s {serial} shell rm -f {remote_path}")  # 可选：清理设备端残留
    #         UiAutomationMixin._run_adb(f"adb -s {serial} pull {remote_path} {local_path}")
    #
    #         # 关键：读取文件内容到内存，再解析
    #         with open(local_path, 'r', encoding='utf-8') as f:
    #             xml_content = f.read()
    #         root = ET.fromstring(xml_content)
    #
    #         logging.debug(f"[DEBUG] UI dumped and parsed from: {local_path}")
    #         return root
    #
    #     except Exception as e:
    #         logging.error(f"Failed to dump or parse UI: {e}")
    #         raise
    #
    #
    #     finally:
    #         if logdir is None:
    #             for attempt in range(3):  # 尝试3次
    #                 try:
    #                     local_path.unlink()
    #                     logging.debug(f"[DEBUG] Successfully deleted temp file: {local_path}")
    #                     break  # 删除成功，跳出循环
    #                 except FileNotFoundError:
    #                     logging.debug(f"[DEBUG] Temp file not found (already deleted): {local_path}")
    #                     break
    #                 except (OSError, PermissionError) as e:
    #                     if attempt == 2:  # 最后一次尝试也失败了
    #                         logging.warning(
    #                             f"[WARN] Failed to delete temp file after 3 attempts: {local_path}. Error: {e}")
    #                     else:
    #                         time.sleep(0.1)  # 等待100ms后重试，比50ms更宽松

    @staticmethod
    def _find_clickable_parent_of_text(root, target_texts: List[str]) -> Optional[Tuple[int, int]]:
        """从 UI 树中查找目标文本的可点击父容器坐标"""
        nodes = []
        for node in root.iter("node"):
            bounds = node.attrib.get("bounds", "")
            coords = list(map(int, re.findall(r"\d+", bounds))) if bounds else []
            nodes.append({
                'node': node,
                'text': node.attrib.get("text", "").strip(),
                'clickable': node.attrib.get("clickable") == "true",
                'bounds_rect': coords
            })

        for item in nodes:
            if not item['text']:
                continue
            for kw in target_texts:
                if kw.lower() in item['text'].lower():
                    child_rect = item['bounds_rect']
                    if len(child_rect) != 4:
                        continue

                    candidates = []
                    for parent in nodes:
                        if not parent['clickable']:
                            continue
                        pr = parent['bounds_rect']
                        if len(pr) != 4:
                            continue
                        if pr[0] <= child_rect[0] and pr[1] <= child_rect[1] and pr[2] >= child_rect[2] and pr[3] >= \
                                child_rect[3]:
                            area = (pr[2] - pr[0]) * (pr[3] - pr[1])
                            candidates.append((area, pr))

                    if candidates:
                        candidates.sort()
                        x = (candidates[0][1][0] + candidates[0][1][2]) // 2
                        y = (candidates[0][1][1] + candidates[0][1][3]) // 2
                        logging.info(f"[DEBUG] Found clickable parent for '{item['text']}' at ({x}, {y})")
                        return x, y

                    if len(child_rect) == 4:
                        x = (child_rect[0] + child_rect[2]) // 2
                        y = (child_rect[1] + child_rect[3]) // 2
                        logging.warning(f"[DEBUG] No clickable parent! Fallback to text coords ({x}, {y})")
                        return x, y

        logging.info("[DEBUG] No matching text found.")
        return None

    @staticmethod
    def _find_ssid_in_list(root, target_ssid: str) -> Optional[Tuple[int, int]]:
        """在 Wi-Fi 列表中查找 SSID（通过 content-desc 或子文本）"""

        def clean_text(text: str) -> str:
            #return re.sub(r"[^a-z0-9]", "", text.strip().lower())
            return text.strip()

        target_clean = clean_text(target_ssid)
        logging.info(f"[DEBUG] Searching for cleaned SSID: '{target_clean}'")

        for node in root.iter("node"):
            if node.attrib.get("clickable") == "true":
                bounds = node.attrib.get("bounds", "")
                coords = list(map(int, re.findall(r"\d+", bounds)))
                if len(coords) != 4:
                    continue
                x = (coords[0] + coords[2]) // 2
                y = (coords[1] + coords[3]) // 2

                # 优先从 content-desc 解析
                content_desc = node.attrib.get("content-desc", "")
                if content_desc:
                    ssid_from_desc = content_desc.split(",")[0].strip()
                    clean_candidate = clean_text(ssid_from_desc)
                    if target_clean in clean_candidate or clean_candidate in target_clean:
                        return x, y

                # 其次从子节点 text 解析
                for child in node.iter("node"):
                    child_text = child.attrib.get("text", "").strip()
                    if child_text:
                        clean_candidate = clean_text(child_text)
                        if target_clean in clean_candidate or clean_candidate in target_clean:
                            logging.info(f"[DEBUG] ✅ Match via child text! Raw: '{child_text}' → Click at ({x}, {y})")
                            return x, y

        logging.info(f"[DEBUG] ❌ SSID '{target_ssid}' not found.")
        return None

    @staticmethod
    def _connect_to_wifi_via_ui(
            serial: str,
            ssid: str,
            password: str = "",
            logdir: Path = None
    ) -> bool:
        """
        Connect SSID via UI
        """
        try:
            # Step 1: Open Wi-Fi Setting
            try:
                temp_mixin = UiAutomationMixin()
                temp_mixin.reset_settings_ui(serial)  # ← 现在可以调用了
            except Exception as e:
                logging.warning(f"[UI Connect] Failed to reset settings UI: {e}")
            success = UiAutomationMixin._go_to_home(serial)
            UiAutomationMixin._open_wifi_settings_page(serial)
            time.sleep(2)

            # Step 2: Click "See all"
            see_all_texts = ["See all", "See all networks", "全部网络", "查看全部", "Show all"]
            logging.info(f"[DEBUG] Looking for 'See all' keywords: {see_all_texts}")
            for retry in range(5):
                logging.info(f"\n[DEBUG] --- Attempt {retry + 1}/2 to find 'See all' ---")
                root = UiAutomationMixin._dump_ui(serial, logdir)
                pos = UiAutomationMixin._find_clickable_parent_of_text(root, see_all_texts)
                if pos:
                    logging.info(f"[INFO] Clicking 'See all' at ({pos[0]}, {pos[1]})")
                    UiAutomationMixin._run_adb(f"adb -s {serial} shell input tap {pos[0]} {pos[1]}")
                    time.sleep(4)
                    break
                time.sleep(2)

            # Step 3: Scroll to bottom
            logging.info("[INFO] Scrolling to bottom of network list...")
            for _ in range(15):
                UiAutomationMixin._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_DPAD_DOWN")
                time.sleep(0.3)

            # Step 4: Find and click target SSID
            for attempt in range(30):
                root = UiAutomationMixin._dump_ui(serial, logdir)
                pos = UiAutomationMixin._find_ssid_in_list(root, ssid)
                logging.info(f"[INFO] Found pos: {pos}")
                if pos:
                    x, y = pos
                    logging.info(f"[INFO] Found SSID '{ssid}' at screen position ({x}, {y}). Tapping directly.")
                    UiAutomationMixin._run_adb(f"adb -s {serial} shell input tap {x} {y}")
                    time.sleep(1.0)

                    # Input password
                    if password:
                        logging.info(f"[INFO] Password required. Entering password.")
                        UiAutomationMixin._run_adb(f"adb -s {serial} shell input text '{password}'")
                        time.sleep(0.5)

                        # Try to Connect
                        try:
                            root_post = UiAutomationMixin._dump_ui(serial, logdir)
                            for node in root_post.iter("node"):
                                text = node.attrib.get("text", "").strip().lower()
                                if text in ["connect", "连接", "ok"]:
                                    bounds = node.attrib.get("bounds", "")
                                    coords = list(map(int, re.findall(r"\d+", bounds)))
                                    if len(coords) == 4:
                                        btn_x = (coords[0] + coords[2]) // 2
                                        btn_y = (coords[1] + coords[3]) // 2
                                        UiAutomationMixin._run_adb(f"adb -s {serial} shell input tap {btn_x} {btn_y}")
                                        logging.info("[INFO] Clicked 'Connect' button.")
                                        break
                            else:
                                logging.info("[INFO] 'Connect' not found. Sending ENTER.")
                                UiAutomationMixin._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_ENTER")
                        except Exception as e:
                            logging.warning(f"[WARN] Failed to click Connect: {e}. Using ENTER fallback.")
                            UiAutomationMixin._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_ENTER")

                        time.sleep(2.0)
                    else:
                        time.sleep(2.0)

                    time.sleep(60)
                    return True

                for _ in range(5):
                    UiAutomationMixin._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_DPAD_UP")
                    time.sleep(0.1)

            return False

        except Exception as e:
            logging.error(f"[UI Connect Error] {e}", exc_info=True)
            return False

    def launch_youtube_tv_and_search(self, serial: str, logdir: Path, query: str = "NASA"):
        """Launch YouTube TV and search for a channel on Android TV."""
        try:
            # Launch
            UiAutomationMixin._run_adb(
                f"adb -s {serial} shell am start -n com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity"
            )
            time.sleep(8)
            self._capture_screenshot(logdir, "tv_youtube_home")

            # Navigate to Search (usually top-right)
            for _ in range(4):  # Move right to "Search"
                UiAutomationMixin._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_DPAD_RIGHT")
                time.sleep(0.5)
            UiAutomationMixin._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_ENTER")
            time.sleep(2)

            # Input text
            UiAutomationMixin._run_adb(f"adb -s {serial} shell input text '{query}'")
            time.sleep(1)
            UiAutomationMixin._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_ENTER")
            time.sleep(5)

            self._capture_screenshot(logdir, "tv_search_results")
            logging.info("✅ YouTube TV search completed.")

            logging.info("⬅️ Exiting Wi-Fi settings UI...")
            for _ in range(3):
                success = UiAutomationMixin._go_to_home(serial)
                time.sleep(1)

            return True
        except Exception as e:
            logging.error(f"❌ YouTube TV automation failed: {e}")
            return False

    def get_wifi_scan_results_via_cmd(self, serial: str) -> List[Tuple[str, int]]:
        """
        use 'cmd wifi list-scan-results' get Wi-Fi scan result.
        """
        try:
            output = self._run_adb_capture_output(
                f"adb -s {serial} shell cmd wifi list-scan-results", timeout=10
            )
            if not output or "BSSID" not in output:
                return []

            ap_list = []
            lines = output.strip().splitlines()
            for line in lines:
                line = line.strip()
                if not line or "BSSID" in line or "------" in line:
                    continue

                parts = re.split(r'\s{2,}', line)
                if len(parts) < 5:
                    continue

                rssi_str = parts[2].strip()
                ssid_raw = parts[4].strip()

                if not ssid_raw or ssid_raw == "''":
                    continue

                ssid = ssid_raw.strip('"').strip("'").strip()
                if not self.wifi_is_valid_ssid(ssid):
                    continue

                try:
                    rssi = int(rssi_str)
                    ap_list.append((ssid, rssi))
                except ValueError:
                    continue

            return ap_list

        except Exception as e:
            logging.error(f"Parse error in scan results: {e}", exc_info=True)
            return []

    @staticmethod
    def _clear_saved_wifi_networks(serial: str):
        """Clear saved Wi-Fi """
        try:
            logging.info(f"🧹 Clearing all saved Wi-Fi networks on {serial}...")

            # Step 1: Try CLI commands
            cli_success = UiAutomationMixin._clear_all_wifi_records(serial)
            if cli_success:
                logging.info("✅ All networks removed via 'cmd wifi'.")
            else:
                # Step 2: CLI failed，use wpa_cli command
                logging.warning("⚠️ CLI method failed. Falling back to wpa_cli disconnect.")
                UiAutomationMixin._disconnect_and_prevent_reconnect(serial)
                time.sleep(2)

            # Step 3: Close Wi-Fi Service
            UiAutomationMixin._run_adb(f"adb -s {serial} shell svc wifi disable")
            time.sleep(2)

            # Step 4: Deleted config files
            UiAutomationMixin._run_adb(f"adb -s {serial} shell rm -f /data/misc/wifi/*.conf")
            UiAutomationMixin._run_adb(f"adb -s {serial} shell rm -f /data/misc/wifi/wpa_supplicant.conf")
            logging.info("✅ Deleted Wi-Fi config files (fallback cleanup).")

            # Step 5: Enable Wi-Fi
            UiAutomationMixin._run_adb(f"adb -s {serial} shell svc wifi enable")
            time.sleep(5)

            logging.info("✅ Wi-Fi cleanup completed.")
        except Exception as e:
            logging.error(f"❌ Failed to clear Wi-Fi networks: {e}")

    @staticmethod
    def _list_saved_networks(serial: str) -> List[int]:
        """使用 'cmd wifi list-saved-networks' 获取所有已保存网络的 ID 列表"""
        try:
            output = UiAutomationMixin._run_adb_capture_output(
                f"adb -s {serial} shell cmd wifi list-saved-networks", timeout=8
            )
            if not output:
                return []
            ids = []
            for line in output.strip().splitlines():
                line = line.strip()
                if line.isdigit():
                    ids.append(int(line))
            return ids
        except Exception as e:
            logging.warning(f"Failed to list saved networks on {serial}: {e}")
            return []

    @staticmethod
    def _clear_all_wifi_records(serial: str) -> bool:
        try:
            logging.info(f"🧹 Using 'cmd wifi forget-network' on {serial}...")

            # 1. Disabled Wi-Fi
            UiAutomationMixin._run_adb(f"adb -s {serial} shell svc wifi disable")
            time.sleep(2)

            # 2. Get networkId（去重 + 排序）
            try:
                output = UiAutomationMixin._run_adb_capture_output(
                    f"adb -s {serial} shell cmd wifi list-saved-networks", timeout=8
                )
                network_ids = sorted(set(int(line.strip()) for line in output.splitlines() if line.strip().isdigit()))
            except Exception as e:
                logging.warning(f"Failed to list networks, assuming none: {e}")
                network_ids = []

            # 3. forget everyone
            if network_ids:
                logging.info(f"Forgetting network IDs: {network_ids}")
                for nid in network_ids:
                    cmd = f"adb -s {serial} shell cmd wifi forget-network {nid}"
                    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,text=True, timeout=5)
                    if "Forget successful" in result.stdout or result.returncode == 0:
                        logging.debug(f"✅ Forgot network {nid}")
                    else:
                        logging.warning(f"⚠️ Failed to forget {nid}: {result.stderr.strip()}")
                    time.sleep(0.3)
            else:
                logging.info("No saved networks to forget.")

            # 4. Delete config files
            UiAutomationMixin._run_adb(f"adb -s {serial} shell rm -f /data/misc/wifi/*.conf")
            UiAutomationMixin._run_adb(f"adb -s {serial} shell rm -f /data/misc/wifi/wpa_supplicant.conf")

            # 5. Enable Wi-Fi
            UiAutomationMixin._run_adb(f"adb -s {serial} shell svc wifi enable")
            time.sleep(5)

            logging.info("✅ Wi-Fi cleanup via 'cmd wifi forget-network' completed.")
            return True

        except Exception as e:
            logging.error(f"❌ Cleanup failed: {e}")
            return False

    def _forget_wifi_via_ui(self, serial: str, target_ssid: str = "None"):
        logging.info(f"🧹 Forgetting Wi-Fi '{target_ssid}' via UI on {serial}...")

        target_ssid = self.get_connected_ssid_via_cli_adb(serial)

        self.reset_settings_ui(serial)
        # Open Wi-Fi Settings
        UiAutomationMixin._open_wifi_settings_page(serial)
        time.sleep(5)

        # Ensure Wi-Fi is on
        state = self._run_adb_capture_output(f"adb -s {serial} shell settings get global wifi_on").strip()
        if state == "0":
            self._run_adb(f"adb -s {serial} shell svc wifi enable")
            time.sleep(5)

        # Step 1: Find and click the SSID (with retry)
        # Step 1: Find and click the SSID (click twice to ensure it works on STB)
        root = self._dump_ui(serial)
        pos = self._find_clickable_parent_of_text(root, [target_ssid])
        if not pos:
            logging.error(f"SSID '{target_ssid}' not found in Wi-Fi list.")
            return False

        x, y = pos
        logging.info(f"✅ Found SSID '{target_ssid}' at ({x}, {y}). Clicking twice...")

        # First click
        self._run_adb(f"adb -s {serial} shell input tap {x} {y}")
        time.sleep(1)

        # Second click (to ensure it registers on STB)
        self._run_adb(f"adb -s {serial} shell input tap {x} {y}")
        time.sleep(2)  # Give time to enter detail page
        detail_indicators = ["Forget", "忘记", "Security", "安全类型", "IP settings", "Signal", target_ssid]
        root_check = self._dump_ui(serial)
        in_detail_page = any(
            self._find_clickable_parent_of_text(root_check, [keyword]) is not None
            for keyword in detail_indicators
        )

        if not in_detail_page:
            logging.error("❌ Still in Wi-Fi list or failed to enter network detail page. Exiting.")
            return False

        logging.info("✅ Confirmed: entered network detail page.")

        # Step 2: Scroll down to reveal 'Forget' button (STB uses DPAD)
        logging.info("⬇️ Scrolling down to reveal 'Forget' button...")
        for i in range(8):  # Press DOWN
            self._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_DPAD_DOWN")
            time.sleep(0.3)

        time.sleep(1)

        # Step 3: Find and click 'Forget'
        root2 = self._dump_ui(serial)
        forget_pos = self._find_clickable_parent_of_text(root2, ["Forget", "忘记", "删除"])
        if forget_pos:
            fx, fy = forget_pos
            logging.info(f"✅ Found 'Forget' at ({fx}, {fy}). Clicking...")
            self._run_adb(f"adb -s {serial} shell input tap {fx} {fy}")
            time.sleep(1)
        else:
            logging.error("❌ 'Forget' button NOT FOUND!")
            return False

        # Step 4: Wait for confirmation dialog and click OK
        logging.info("🔍 Waiting for 'Forget network' confirmation dialog...")
        for _ in range(5):  # 最多等待 10 秒
            root3 = self._dump_ui(serial)
            ok_pos = self._find_clickable_parent_of_text(root3, ["OK", "确认", "确定"])
            if ok_pos:
                ox, oy = ok_pos
                logging.info(f"✅ Found 'OK' at ({ox}, {oy}). Clicking...")
                self._run_adb(f"adb -s {serial} shell input tap {ox} {oy}")
                logging.info("✅ Successfully forgot network via UI.")
                break
            time.sleep(1)

        else:
            logging.error("❌ 'OK' button not found in confirmation dialog!")
            return False

        logging.info("⬅️ Exiting Wi-Fi settings UI...")
        for _ in range(3):
            self._run_adb(f"adb -s {serial} shell input keyevent KEYCODE_BACK")
            success = UiAutomationMixin._go_to_home(serial)
            time.sleep(1)

        logging.info("✅ Exited Wi-Fi settings UI.")
        return True

    @staticmethod
    def _add_manual_wifi_network(
            serial: str,
            ssid: str,
            security: str,
            password: Optional[str] = None,
            logdir: Optional[Path] = None
    ) -> bool:
        import time
        import re

        # --- Helper Functions ---
        def _execute_adb_command(cmd: str):
            UiAutomationMixin._run_adb(f"adb -s {serial} {cmd}")

        def _dump_ui():
            return UiAutomationMixin._dump_ui(serial, logdir)

        def _tap_text(root, keywords: List[str]) -> bool:
            pos = UiAutomationMixin._find_clickable_parent_of_text(root, keywords)
            if pos:
                x, y = pos
                _execute_adb_command(f"shell input tap {x} {y}")
                return True
            return False

        def _get_center(node) -> Tuple[int, int]:
            bounds = node.attrib.get("bounds", "")
            coords = list(map(int, re.findall(r"\d+", bounds)))
            if len(coords) == 4:
                return (coords[0] + coords[2]) // 2, (coords[1] + coords[3]) // 2
            return 0, 0

        def _escape_text_for_input(text: str) -> str:
            text = text.replace(" ", "%s")
            text = text.replace("'", "\\'")
            return text

        def _take_screenshot(name: str):
            if logdir:
                path = logdir / f"{name}_{int(time.time())}.png"
                _execute_adb_command(f"exec-out screencap -p > '{path}'")

        try:
            logging.info(f"Starting manual connect to hidden SSID: {ssid}, security: {security}")

            # --- Step 1: Open Wi-Fi settings ---
            if not UiAutomationMixin._open_wifi_settings_page(serial):
                logging.error("Failed to open Wi-Fi settings page")
                _take_screenshot("fail_open_wifi")
                return False
            time.sleep(3)
            _take_screenshot("wifi_settings_page")

            # --- Step 2: Click "Add new network" BUTTON ---
            # We are now on the main Wi-Fi settings page (showing network list)
            add_net_clicked = False
            for attempt in range(5):
                root = _dump_ui()
                # DEBUG: Log all texts to see what's actually on screen
                all_texts = [node.attrib.get("text", "") for node in root.iter("node") if node.attrib.get("text")]
                logging.info(
                    f"[DEBUG] Attempt {attempt + 1} - Visible texts: {[t for t in all_texts if t.strip()][:10]}")

                add_net_keywords = [
                    "Add new network", "Add network", "Add Wi-Fi network",
                    "Join other network", "Other networks", "更多网络",
                    "连接其他网络", "手动添加网络", "添加网络",
                    "+", "＋", "添加"
                ]

                if _tap_text(root, add_net_keywords):
                    logging.info("✅ Successfully clicked 'Add new network' button")
                    add_net_clicked = True
                    break
                else:
                    logging.warning(f"'Add new network' not found on attempt {attempt + 1}")
                    # Try scrolling down in case button is off-screen
                    _execute_adb_command("shell input swipe 500 1000 500 300 300")
                    time.sleep(2)

            if not add_net_clicked:
                logging.error("❌ Failed to find and click 'Add new network' button")
                _take_screenshot("add_network_not_found")
                return False

            # --- Step 3: Wait for SSID input page ---
            ssid_input_page = False
            for wait_attempt in range(8):  # Wait up to 8 seconds
                time.sleep(1)
                root = _dump_ui()
                all_texts = {node.attrib.get("text", "") for node in root.iter("node")}
                if "Enter name of Wi-Fi network" in all_texts:
                    ssid_input_page = True
                    logging.info("✅ SSID input page loaded")
                    break

            if not ssid_input_page:
                logging.error("❌ SSID input page did not appear after clicking 'Add new network'")
                _take_screenshot("ssid_input_not_loaded")
                return False

            _take_screenshot("ssid_input_page")

            # --- Step 4: Input SSID ---
            ssid_input_found = False
            for node in root.iter("node"):
                text = node.attrib.get("text", "")
                hint = node.attrib.get("hint", "")
                if "Enter name of Wi-Fi network" in (text, hint):
                    x, y = _get_center(node)
                    _execute_adb_command(f"shell input tap {x} {y}")
                    time.sleep(0.5)
                    escaped_ssid = _escape_text_for_input(ssid)
                    logging.info(f"Entering SSID: {ssid}")
                    _execute_adb_command(f"shell input text '{escaped_ssid}'")
                    ssid_input_found = True
                    break

            if not ssid_input_found:
                logging.error("SSID input field not found")
                _take_screenshot("no_ssid_field")
                return False

            # --- Step 5: Click Next/Connect ---
            next_keywords = ["Next", "Connect", "OK", "下一步", "确定", "继续"]
            if not _tap_text(_dump_ui(), next_keywords):
                logging.warning("Next button not found, trying ENTER key")
                _execute_adb_command("shell input keyevent KEYCODE_ENTER")
            time.sleep(2)

            # --- Step 6: Select Security Type ---
            root = _dump_ui()
            all_texts = [node.attrib.get("text", "") for node in root.iter("node")]

            # Check if we are on the security selection page
            if any("Type of security" in txt for txt in all_texts):
                logging.info("✅ Found 'Type of security' page")

                # Define mapping from test case security to UI text
                security_mapping = {
                    "None": ["None"],
                    "Enhanced Open": ["Enhanced Open"],
                    "WEP": ["WEP"],
                    "WPA/WPA2": ["WPA/WPA2-Personal"],
                    "WPA3": ["WPA3-Personal"]
                }

                target_options = security_mapping.get(security, [security])
                logging.info(f"Trying to select security: {target_options}")

                if _tap_text(root, target_options):
                    logging.info(f"✅ Successfully selected security: {security}")
                else:
                    logging.warning(f"⚠️ Could not find security option: {target_options}")

            # --- Step 7: Input Password if needed ---
            if password and password.strip():
                logging.info(f"Inputting password: {password}")

                # Wait for password page
                password_page_found = False
                for wait_attempt in range(5):
                    time.sleep(1)
                    root = _dump_ui()
                    all_texts = [node.attrib.get("text", "") for node in root.iter("node")]
                    if any("Enter password" in txt for txt in all_texts):
                        password_page_found = True
                        break

                if not password_page_found:
                    logging.warning("Password page not detected, proceeding anyway...")

                password_input_found = False

                # Method 1: Try to find by class and position
                for node in root.iter("node"):
                    node_class = node.attrib.get("class", "")
                    clickable = node.attrib.get("clickable", "")
                    focusable = node.attrib.get("focusable", "")

                    if ("EditText" in node_class or "TextView" in node_class) and \
                            clickable == "true" and focusable == "true":

                        # Additional check: should be empty (no text)
                        if node.attrib.get("text", "") == "":
                            x, y = _get_center(node)
                            _execute_adb_command(f"shell input tap {x} {y}")
                            time.sleep(0.5)
                            escaped_pwd = _escape_text_for_input(password)
                            _execute_adb_command(f"shell input text '{escaped_pwd}'")
                            password_input_found = True
                            logging.info("✅ Password input field found by class properties")
                            break

                # Method 2: Fallback to fixed position if not found
                if not password_input_found:
                    logging.info("Using fallback: clicking fixed password position")
                    _execute_adb_command("shell input tap 540 650")  # Middle of screen, adjust as needed
                    time.sleep(0.5)
                    escaped_pwd = _escape_text_for_input(password)
                    _execute_adb_command(f"shell input text '{escaped_pwd}'")

                    # --- Step: Submit password using multiple fallback strategies ---
                    def _submit_password_input(serial, execute_adb_func, dump_ui_func, timeout=8):
                        """
                        Robustly submit password input using multiple strategies.
                        Works across different devices, resolutions, and IMEs.
                        """
                        import time
                        import logging

                        # Strategy 1: Try KEYCODE_ENTER (most universal)
                        logging.info("🔐 [Strategy 1] Submitting via KEYCODE_ENTER")
                        execute_adb_func("shell input keyevent KEYCODE_ENTER")
                        time.sleep(2)

                        # Check if we've left the password page
                        root = dump_ui_func()
                        all_texts = [node.attrib.get("text", "") for node in root.iter("node")]
                        if not any("Enter password" in t or "password" in t.lower() for t in all_texts):
                            logging.info("✅ Password submitted successfully via KEYCODE_ENTER")
                            return True

                        # Strategy 2: Dynamic coordinate click (bottom-right area)
                        logging.info("🔐 [Strategy 2] Trying dynamic coordinate click")

                        # Get logical screen size safely
                        try:
                            wm_output = UiAutomationMixin._run_adb(f"adb -s {serial} shell wm size")
                            lines = wm_output.strip().split('\n')
                            size_line = lines[-1]  # Usually last line has the size
                            if 'x' in size_line:
                                w, h = map(int, size_line.split()[-1].split('x'))
                            else:
                                w, h = 1080, 2340
                        except Exception as e:
                            logging.warning(f"Failed to parse screen size, using default: {e}")
                            w, h = 1080, 2340

                        logging.info(f"Screen logical size: {w}x{h}")

                        # Click bottom-right corner (where IME confirm button usually is)
                        confirm_x = int(w * 0.90)  # 90% from left
                        confirm_y = int(h * 0.95)  # 95% from top
                        logging.info(f"Clicking IME confirm at ({confirm_x}, {confirm_y})")
                        execute_adb_func(f"shell input tap {confirm_x} {confirm_y}")
                        time.sleep(2)

                        # Re-check page
                        root = dump_ui_func()
                        all_texts = [node.attrib.get("text", "") for node in root.iter("node")]
                        if not any("Enter password" in t or "password" in t.lower() for t in all_texts):
                            logging.info("✅ Password submitted successfully via coordinate click")
                            return True

                        # Strategy 3: Try common IME button texts
                        logging.info("🔐 [Strategy 3] Trying IME button text match")
                        ime_keywords = ["✓", "→", "Go", "Next", "Done", "继续", "确定", "前往"]
                        for keyword in ime_keywords:
                            for node in root.iter("node"):
                                if keyword in node.attrib.get("text", ""):
                                    bounds = node.attrib.get("bounds", "")
                                    import re
                                    coords = list(map(int, re.findall(r"\d+", bounds)))
                                    if len(coords) == 4:
                                        x = (coords[0] + coords[2]) // 2
                                        y = (coords[1] + coords[3]) // 2
                                        execute_adb_func(f"shell input tap {x} {y}")
                                        time.sleep(2)
                                        logging.info(f"Clicked IME button: '{keyword}'")

                                        # Final check
                                        root = dump_ui_func()
                                        all_texts = [n.attrib.get("text", "") for n in root.iter("node")]
                                        if not any("Enter password" in t for t in all_texts):
                                            logging.info("✅ Password submitted via IME text button")
                                            return True
                                        break

                        logging.error("❌ All password submission strategies failed")
                        return False

                    # --- Call the robust submit function ---
                    logging.info("🔐 Submitting password with multi-strategy approach")
                    password_submitted = _submit_password_input(
                        serial=serial,
                        execute_adb_func=_execute_adb_command,
                        dump_ui_func=_dump_ui
                    )

                    if not password_submitted:
                        logging.warning("Password submission may have failed. Continuing anyway...")

            time.sleep(30)
            return True

        except Exception as e:
            logging.exception(f"Error in _add_manual_wifi_network: {e}")
            _take_screenshot("exception")
            return False

    @staticmethod
    def _check_network_ping(serial: str):
        """
           Check network connectivity by pinging 8.8.8.8.

           Performs a ping test and optionally retries on failure to handle
           slow network initialization.

           Args:
               serial (str): ADB serial of the target device.
               retries (int): Number of retry attempts after initial failure.
               delay_before_check (float): Seconds to sleep before the first ping.

           Returns:
               bool: True if ping succeeds in any attempt, False otherwise.
       """
        for attempt in range(2):
            try:
                output = UiAutomationMixin._run_adb_capture_output(
                    f"adb -s {serial} shell ping -c 10 8.8.8.8",
                    timeout=10
                )
                # 检查是否收到回复（典型成功输出包含 "bytes from 8.8.8.8"）
                if "bytes from 8.8.8.8" in output or "64 bytes from" in output:
                    logging.info("Ping succeeded")
                    return True
                else:
                    logging.warning(f"Ping failed (attempt {attempt + 1}), output:\n{output}")
            except Exception as e:
                logging.warning(f"Ping command failed (attempt {attempt + 1}): {e}")

            if attempt == 0:
                time.sleep(10)

        return False

    def reset_settings_ui(self, serial: str, timeout: int = 5) -> bool:
        """
        通用方法：强制退出卡死的 Wi-Fi 设置界面，并返回到干净的主设置页面或 Home。

        支持多种 Android DUT：
          - 标准 Android (com.android.settings)
          - Android TV (com.android.tv.settings)
          - Google TV / Chromecast
          - 华硕、小米等定制 ROM

        复用本类已有的 _run_adb 和 _go_to_home 方法。

        Args:
            serial (str): ADB 设备序列号
            timeout (int): 每步操作等待时间（秒）

        Returns:
            bool: True if success, False otherwise
        """
        # Step 1: 获取所有已安装的包（使用 _run_adb_capture_output 复用现有逻辑）
        try:
            output = self._run_adb_capture_output(
                f"adb -s {serial} shell pm list packages", timeout=timeout + 5
            )
            if not output:
                logging.warning(f"[UI Reset] Failed to list packages on {serial}")
                installed_packages = set()
            else:
                installed_packages = {
                    line.strip().replace("package:", "")
                    for line in output.splitlines()
                    if line.strip().startswith("package:")
                }
        except Exception as e:
            logging.error(f"[UI Reset] Exception while listing packages: {e}")
            installed_packages = set()

        # Step 2: 定义候选的 (package, activity) 列表，按优先级排序
        candidates = [
            # Android TV (Google 官方)
            ("com.android.tv.settings", ".MainSettings"),
            ("com.android.tv.settings", ".settings.MainSettings"),

            # Standard Android (Phone/Tablet)
            ("com.android.settings", ".Settings"),
            ("com.android.settings", ".homepage.SettingsHomepageActivity"),

            # Google TV / Chromecast
            ("com.google.android.tv.settings", ".MainSettings"),
            ("com.google.android.tv.settings", ".homepage.SettingsHomepageActivity"),

            # ASUS TV
            ("com.asus.tv.settings", ".MainActivity"),
            ("com.asus.tv.settings", ".SettingsActivity"),

            # Xiaomi / MIUI
            ("com.miui.settings", ".Settings"),

            # Samsung
            ("com.sec.android.app.settings", ".Settings"),
        ]

        # Step 3: 尝试 force-stop + restart 每个存在的候选
        for package, activity in candidates:
            if package not in installed_packages:
                continue  # 跳过未安装的包

            try:
                # 强制停止整个应用（复用 _run_adb）
                self._run_adb(f"adb -s {serial} shell am force-stop {package}")
                time.sleep(1)

                # 尝试启动主界面（复用 _run_adb）
                self._run_adb(f"adb -s {serial} shell am start -n {package}{activity}")
                time.sleep(timeout)

                logging.info(f"[UI Reset] Successfully restarted {package}{activity} on {serial}")
                return True

            except Exception as e:
                logging.debug(f"[UI Reset] Failed to restart {package}{activity}: {e}")
                continue

        # Step 4: 所有 Settings 重启都失败 → 回退到 Home Screen（保底方案）
        # 直接复用已有的 _go_to_home 静态方法！
        logging.warning("[UI Reset] All Settings restart attempts failed. Falling back to Home.")
        return UiAutomationMixin._go_to_home(serial, timeout=timeout)