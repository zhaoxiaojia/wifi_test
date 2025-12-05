import logging
import os
import re
import subprocess
import threading
import time
import asyncio
import random
import pytest
import telnetlib
from dataclasses import dataclass
from typing import Optional, Sequence
from src.tools.ixchariot import ix
from threading import Thread
from src.tools.config_loader import load_config
from src.tools.router_tool.router_performance import handle_expectdata
from src.util.constants import is_database_debug_enabled
from src.tools.connect_tool.command_batch import CommandBatch, CommandRunner, CommandExecutionError, CommandTimeoutError
from src.tools.performance_result import PerformanceResult

lock = threading.Lock()


@dataclass
class IperfMetrics:
    """
    Iperf metrics.

    -------------------------
    Returns
    -------------------------
    None
        This class does not return a value.
    """
    throughput_mbps: Optional[float]
    latency_ms: Optional[float] = None
    packet_loss: Optional[str] = None

    def formatted_throughput(self) -> Optional[str]:
        """
        Formatted throughput.

        -------------------------
        Returns
        -------------------------
        Optional[str]
            A value of type ``Optional[str]``.
        """
        if self.throughput_mbps is None:
            return None
        return f"{self.throughput_mbps:.1f}"


class dut():
    """
    Dut.

    -------------------------
    It runs shell commands on the target device using ADB helpers and captures the output.
    It executes external commands via Python's subprocess module.
    It logs information for debugging or monitoring purposes.
    It introduces delays to allow the device to process commands.

    -------------------------
    Returns
    -------------------------
    None
        This class does not return a value.
    """
    count = 0
    DMESG_COMMAND = 'dmesg -S'
    CLEAR_DMESG_COMMAND = 'dmesg -c'

    SETTING_ACTIVITY_TUPLE = 'com.android.tv.settings', '.MainSettings'
    MORE_SETTING_ACTIVITY_TUPLE = 'com.droidlogic.tv.settings', '.more.MorePrefFragmentActivity'

    SKIP_OOBE = "pm disable com.google.android.tungsten.setupwraith;settings put secure user_setup_complete 1;settings put global device_provisioned 1;settings put secure tv_user_setup_complete 1"
    IPERF_KILL = 'killall -9 {}'
    IPERF_WIN_KILL = 'taskkill /im {}.exe -f'

    def __init__(self) -> None:
        """
        Initialize common DUT state.

        This sets baseline attributes that are shared across adb/telnet
        implementations so that tests can rely on them being present.
        """
        self.rssi_num = -1
        self.freq_num = 0

    def _is_performance_debug_enabled(self) -> bool:
        """
        Return True when database debug mode should affect throughput logic.

        Database debug mode is only honored for performance‑type runs
        (RVR/RVO/Performance). Compatibility and other tests are not
        affected even if the global debug flag is enabled.
        """
        if not is_database_debug_enabled():
            return False
        selected = getattr(pytest, "selected_test_types", set())
        return any(kind in {"RVR", "RVO", "PERFORMANCE"} for kind in selected)
    
    def _ensure_performance_result(self) -> None:
        """
        Lazily create the shared PerformanceResult instance used for
        throughput logging when it is first needed.
        """
        if getattr(pytest, "testResult", None) is not None:
            return
        logdir = getattr(pytest, "_result_path", None) or os.getcwd()
        repeat_times = getattr(pytest, "_testresult_repeat_times", 0)
        pytest.testResult = PerformanceResult(logdir, [], repeat_times)

    @staticmethod
    def _parse_iperf_params(cmd: str) -> tuple[int, int]:
        """
        Parse Iperf params.

        -------------------------
        Parameters
        -------------------------
        cmd : Any
            Command string to parse or execute.

        -------------------------
        Returns
        -------------------------
        tuple[int, int]
            A value of type ``tuple[int, int]``.
        """
        t_match = re.search(r'-t\s+(\d+)', cmd)
        p_match = re.search(r'-P\s+(\d+)', cmd)
        test_time = int(t_match.group(1)) if t_match else 30
        pair = int(p_match.group(1)) if p_match else 1
        return test_time, pair

    @staticmethod
    def _is_udp_command(cmd: str) -> bool:
        """
        Is udp command.

        -------------------------
        Parameters
        -------------------------
        cmd : Any
            Command string to parse or execute.

        -------------------------
        Returns
        -------------------------
        bool
            A value of type ``bool``.
        """
        return bool(re.search(r'(^|\s)-u(\s|$)', cmd))

    @staticmethod
    def _calculate_iperf_wait_time(test_time: int) -> int:
        """
        Calculate Iperf wait time.

        -------------------------
        Parameters
        -------------------------
        test_time : Any
            Duration of an iperf test run in seconds.

        -------------------------
        Returns
        -------------------------
        int
            A value of type ``int``.
        """
        safe_time = max(test_time, 1)
        buffer = max(15, min(120, safe_time // 2))
        return safe_time + buffer

    @staticmethod
    def _convert_bandwidth_to_mbps(value: float, unit: str) -> Optional[float]:
        """
        Convert bandwidth to mbps.

        -------------------------
        Parameters
        -------------------------
        value : Any
            Numeric value used in calculations.
        unit : Any
            Unit of measurement associated with a value.

        -------------------------
        Returns
        -------------------------
        Optional[float]
            A value of type ``Optional[float]``.
        """
        unit = unit.lower()
        if 'bits/sec' not in unit:
            return None
        if unit.startswith('g'):
            return value * 1000
        if unit.startswith('m'):
            return value
        if unit.startswith('k'):
            return value / 1000
        if unit.startswith('bits'):
            return value / 1_000_000
        return None

    @staticmethod
    def _sanitize_iperf_line(text: str) -> str:
        """
        Sanitize Iperf line.

        -------------------------
        Parameters
        -------------------------
        text : Any
            Text to input into the device.

        -------------------------
        Returns
        -------------------------
        str
            A value of type ``str``.
        """
        if not text:
            return ""
        without_ansi = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
        cleaned = re.sub(r'[\x00-\x1f\x7f]', '', without_ansi)
        return cleaned.strip()

    @staticmethod
    def _extract_udp_metrics(line: str) -> Optional[IperfMetrics]:
        """
        Extract udp metrics.

        -------------------------
        Parameters
        -------------------------
        line : Any
            The ``line`` parameter.

        -------------------------
        Returns
        -------------------------
        Optional[IperfMetrics]
            A value of type ``Optional[IperfMetrics]``.
        """
        sanitized = dut._sanitize_iperf_line(line)
        jitter_match = re.search(r'(\d+(?:\.\d+)?)\s*ms', sanitized, re.IGNORECASE)
        loss_match = re.search(r'(\d+\s*/\s*\d+\s*\(\s*\d+(?:\.\d+)?\s*%?\s*\))', sanitized)
        if not jitter_match or not loss_match:
            return None
        bandwidth_match = re.search(r'(\d+(?:\.\d+)?)\s*([KMG]?bits/sec)', sanitized, re.IGNORECASE)
        throughput = None
        if bandwidth_match:
            throughput = dut._convert_bandwidth_to_mbps(
                float(bandwidth_match.group(1)), bandwidth_match.group(2)
            )
        packet_loss = re.sub(r'\s+', '', loss_match.group(1))
        try:
            jitter = float(jitter_match.group(1))
        except ValueError:
            jitter = None
        return IperfMetrics(throughput, jitter, packet_loss)

    IW_LINNK_COMMAND = 'iw dev wlan0 link'
    IX_ENDPOINT_COMMAND = "monkey -p com.ixia.ixchariot 1"
    STOP_IX_ENDPOINT_COMMAND = "am force-stop com.ixia.ixchariot"
    CMD_WIFI_CONNECT = 'cmd wifi connect-network {} {} {}'
    CMD_WIFI_HIDE = ' -h'
    CMD_WIFI_STATUS = 'cmd wifi status'
    CMD_WIFI_START_SAP = 'cmd wifi start-softsap {} {} {} -b {}'
    CMD_WIFI_STOP_SAP = 'cmd wifi stop-softsap'
    CMD_WIFI_LIST_NETWORK = "cmd wifi list-networks |grep -v Network |awk '{print $1}'"
    CMD_WIFI_FORGET_NETWORK = 'cmd wifi forget-network {}'

    CMD_PING = 'ping -n {}'
    SVC_WIFI_DISABLE = 'svc wifi disable'
    SVC_WIFI_ENABLE = 'svc wifi enable'

    SVC_BLUETOOTH_DISABLE = 'svc bluetooth disable'
    SVC_BLUETOOTH_ENABLE = 'svc bluetooth enable'

    MCS_RX_GET_COMMAND = 'iwpriv wlan0 get_last_rx'
    MCS_RX_CLEAR_COMMAND = 'iwpriv wlan0 clear_last_rx'
    MCS_TX_GET_COMMAND = 'iwpriv wlan0 get_rate_info'
    MCS_TX_KEEP_GET_COMMAND = "'for i in `seq 1 10`;do iwpriv wlan0 get_rate_info;sleep 6;done ' & "
    POWERRALAY_COMMAND_FORMAT = './tools/powerRelay /dev/tty{} -all {}'

    GET_COUNTRY_CODE = 'iw reg get'
    SET_COUNTRY_CODE_FORMAT = 'iw reg set {}'

    OPEN_INFO = r'<node index="0" text="Hotspot name" resource-id="android:id/title" class="android.widget.TextView" package="com.(.*?).tv.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="true"'
    CLOSE_INFO = r'<node index="0" text="Hotspot name" resource-id="android:id/title" class="android.widget.TextView" package="com.(.*?).tv.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="false"'

    PLAYERACTIVITY_REGU = 'am start -n com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity -d https://www.youtube.com/watch?v={}'
    VIDEO_TAG_LIST = [
        {'link': 'r_gV5CHOSBM', 'name': '4K Amazon'},  # 4k
        {'link': 'vX2vsvdq8nw', 'name': '4K HDR 60FPS Sniper Will Smith'},  # 4k hrd 60 fps
        {'link': '-ZMVjKT3-5A', 'name': 'NBC News (vp9)'},  # vp9
        {'link': 'LXb3EKWsInQ', 'name': 'COSTA RICA IN 4K 60fps HDR (ULTRA HD) (vp9)'},  # vp9
        {'link': 'b6fzbyPoNXY', 'name': 'Las Vegas Strip at Night in 4k UHD HLG HDR (vp9)'},  # vp9
        {'link': 'AtZrf_TWmSc', 'name': 'How to Convert,Import,and Edit AVCHD Files for Premiere (H264)'},  # H264
        {'link': 'LXb3EKWsInQ', 'name': 'COSTA RICA IN 4K 60fps HDR(ultra hd) (4k 60fps)'},  # 4k 60fps
        {'link': 'NVhmq-pB_cs', 'name': 'Mr Bean 720 25fps (720 25fps)'},
        {'link': 'bcOgjyHb_5Y', 'name': 'paid video'},
        {'link': 'rf7ft8-nUQQ', 'name': 'stress video'}
    ]

    WIFI_BUTTON_TAG = 'Available networks'

    def __init__(self):
        """
        Init.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.serialnumber = 'executer'
        cfg = load_config(refresh=True)
        rvr_cfg = cfg.get('rvr', {})
        self.rvr_tool = rvr_cfg.get('tool', 'iperf')
        iperf_cfg = rvr_cfg.get('iperf', {})
        self.iperf_server_cmd = iperf_cfg.get('server_cmd', 'iperf -s -w 2m -i 1')
        self.iperf_client_cmd = iperf_cfg.get('client_cmd', 'iperf -c {ip} -w 2m -i 1 -t 30 -P 5')
        self.iperf_test_time, self.pair = self._parse_iperf_params(self.iperf_client_cmd)
        self.iperf_wait_time = self._calculate_iperf_wait_time(self.iperf_test_time)
        self.repest_times = int(rvr_cfg.get('repeat', 0))
        self._dut_ip = ''
        self._pc_ip = ''
        self.ip_target = ''
        self.rvr_result = None
        self.throughput_threshold = float(rvr_cfg.get('throughput_threshold', 0))
        self.skip_tx = False
        self.skip_rx = False
        self.iperf_server_log_list: list[str] = []
        self._current_udp_mode = False
        encoding = 'gb2312' if getattr(pytest, "win_flag", False) else "utf-8"
        self.command_runner = CommandRunner(encoding=encoding)
        if self.rvr_tool == 'iperf':
            cmds = f"{self.iperf_server_cmd} {self.iperf_client_cmd}"
            self.test_tool = 'iperf3' if 'iperf3' in cmds else 'iperf'
            self.tool_path = iperf_cfg.get('path', '')
            self._current_udp_mode = self._is_udp_command(self.iperf_client_cmd) or self._is_udp_command(
                self.iperf_server_cmd
            )
            logging.info(f'test_tool {self.test_tool}')

        if self.rvr_tool == 'ixchariot':
            self.ix = ix()
            ix_cfg = rvr_cfg.get('ixchariot', {})
            self.test_tool = ix_cfg
            self.script_path = ix_cfg.get('path', '')
            logging.info(f'path {self.script_path}')
            logging.info(f'test_tool {self.test_tool}')
            self.ix.modify_tcl_script(
                "set ixchariot_installation_dir ",
                f"set ixchariot_installation_dir \"{self.script_path}\"\n",
            )

    def ping(
        self,
        interface=None,
        hostname="www.baidu.com",
        interval_in_seconds=1,
        ping_time_in_seconds=5,
        timeout_in_seconds=10,
        size_in_bytes=None,
    ):
        """Run an ICMP ping on the DUT side and return True when packet loss is acceptable."""

        if not hostname or not isinstance(hostname, str):
            logging.error("Ping checkpoint missing hostname")
            return False
        interval = max(float(interval_in_seconds or 1), 0.2)
        duration = max(float(ping_time_in_seconds or 1), interval)
        count = max(int(duration / interval), 1)
        timeout = max(int(timeout_in_seconds or 1), 1) + count

        if interface:
            if size_in_bytes:
                cmd = f"ping -i {interval:.2f} -I {interface} -c {count} -s {size_in_bytes} {hostname}"
            else:
                cmd = f"ping -i {interval:.2f} -I {interface} -c {count} {hostname}"
        else:
            if size_in_bytes:
                cmd = f"ping -i {interval:.2f} -c {count} -s {size_in_bytes} {hostname}"
            else:
                cmd = f"ping -i {interval:.2f} -c {count} {hostname}"

        logging.debug("Ping command: %s", cmd)
        try:
            output = self.checkoutput(cmd)
        except Exception as exc:  # pragma: no cover - transports differ per DUT
            logging.error("Ping command failed: %s", exc)
            return False
        if not output:
            return False

        # Inspect tracked return code/stderr to flag remote ping failures.
        last_code = getattr(self, "_last_command_returncode", 0)
        stderr_output = getattr(self, "_last_command_stderr", "")
        if last_code:
            logging.debug("Ping exit code %s stderr: %s", last_code, stderr_output.strip())
            return False

        lowered = output.lower()
        error_lowered = stderr_output.lower()
        if "unknown host" in lowered or "name or service not known" in lowered:
            logging.debug("Ping reported unknown host: %s", hostname)
            return False
        if "unknown host" in error_lowered or "name or service not known" in error_lowered:
            logging.debug("Ping stderr reported unknown host: %s", hostname)
            return False

        loss_match = re.search(r"(\d+)% packet loss", output)
        if loss_match:
            packet_loss = int(loss_match.group(1))
            logging.debug("Ping packet loss = %s%%", packet_loss)
            return packet_loss == 0

        logging.debug("Ping output unparsable:\n%s", output)
        return False

    @property
    def dut_ip(self):
        """
        Dut ip.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if self._dut_ip == '': self._dut_ip = self.get_dut_ip()
        return self._dut_ip

    @dut_ip.setter
    def dut_ip(self, value):
        """
        Dut ip.

        -------------------------
        Parameters
        -------------------------
        value : Any
            Numeric value used in calculations.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self._dut_ip = value

    @property
    def pc_ip(self):
        """
        Pc ip.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if self._pc_ip == '': self._pc_ip = self.get_pc_ip()
        self.ip_target = '.'.join(self._pc_ip.split('.')[:3])
        return self._pc_ip

    @pc_ip.setter
    def pc_ip(self, value):
        """
        Pc ip.

        -------------------------
        Parameters
        -------------------------
        value : Any
            Numeric value used in calculations.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self._pc_ip = value

    @property
    def freq_num(self):
        """
        Freq num.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        return self._freq_num

    @freq_num.setter
    def freq_num(self, value):
        """
        Freq num.

        -------------------------
        Parameters
        -------------------------
        value : Any
            Numeric value used in calculations.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self._freq_num = int(value)
        self.channel = int((self._freq_num - 2412) / 5 + 1 if self._freq_num < 3000 else (self._freq_num - 5000) / 5)

    @staticmethod
    def _format_result_row(values):
        """
        Format result row.

        -------------------------
        Parameters
        -------------------------
        values : Any
            The ``values`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """

        def normalize(value: Optional[object]) -> str:
            """
            Normalize.

            -------------------------
            Parameters
            -------------------------
            value : Any
                Numeric value used in calculations.

            -------------------------
            Returns
            -------------------------
            str
                A value of type ``str``.
            """
            if value is None:
                return ''
            text = str(value)
            if not text:
                return ''
            if any(ch in text for ch in {',', '"', '\n', '\r'}):
                escaped = text.replace('"', '""')
                return f'"{escaped}"'
            return text

        return ','.join(normalize(value) for value in values)

    def _build_throughput_result_values(
            self,
            router_info,
            protocol: str,
            direction: str,
            db_set: str,
            corner: str,
            mcs_value: Optional[str],
            throughput_values: Sequence[Optional[str]],
            expect_rate,
            latency_value,
            packet_loss_value,
    ):
        """
        Build throughput result values.

        -------------------------
        Parameters
        -------------------------
        router_info : Any
            The ``router_info`` parameter.
        protocol : Any
            The ``protocol`` parameter.
        direction : Any
            The ``direction`` parameter.
        db_set : Any
            The ``db_set`` parameter.
        corner : Any
            The ``corner`` parameter.
        mcs_value : Any
            The ``mcs_value`` parameter.
        throughput_values : Any
            The ``throughput_values`` parameter.
        expect_rate : Any
            The ``expect_rate`` parameter.
        latency_value : Any
            The ``latency_value`` parameter.
        packet_loss_value : Any
            The ``packet_loss_value`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """

        def _first_token(text: str) -> str:
            """
            First token.

            -------------------------
            Parameters
            -------------------------
            text : Any
                Text to input into the device.

            -------------------------
            Returns
            -------------------------
            str
                A value of type ``str``.
            """
            return text.split()[0] if text else text

        values = [
            self.serialnumber,
            'Throughput',
            _first_token(router_info.wireless_mode),
            _first_token(router_info.band),
            _first_token(router_info.bandwidth),
            'Rate_Adaptation',
            router_info.channel,
            protocol,
            direction,
            'NULL',
            db_set,
            self.rssi_num,
            corner,
            mcs_value if mcs_value else 'NULL',
        ]
        for entry in throughput_values:
            values.append('' if entry is None else entry)
        values.extend([
            expect_rate,
            latency_value,
            packet_loss_value,
        ])
        return values

    def _normalize_throughput_cells(self, entries: list[str]) -> list[str]:
        """
        Normalize throughput cells.

        -------------------------
        Parameters
        -------------------------
        entries : Any
            The ``entries`` parameter.

        -------------------------
        Returns
        -------------------------
        list[str]
            A value of type ``list[str]``.
        """
        total_runs = max(1, self.repest_times + 1)
        sanitized = entries[:total_runs]
        while len(sanitized) < total_runs:
            sanitized.append('')
        return [entry if entry is not None else '' for entry in sanitized]

    def step(func):
        """
        Step.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        func : Any
            The ``func`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """

        def wrapper(*args, **kwargs):
            """
            Wrapper.

            -------------------------
            It logs information for debugging or monitoring purposes.

            -------------------------
            Returns
            -------------------------
            Any
                The result produced by the function.
            """
            logging.info('-' * 80)
            dut.count += 1
            logging.info(f"Test Step {dut.count}:")
            logging.info(func.__name__)
            info = func(*args, **kwargs)

            logging.info('-' * 80)
            return info

        return wrapper

    def checkoutput_term(self, command):
        """
        Checkoutput term.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It executes external commands via Python's subprocess module.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        command : Any
            The ``command`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        logging.debug(f"command:{command}")
        try:
            result = self.command_runner.run(command, shell=True)
            # Track last host command status for later diagnostics.
            self._last_command_stdout = result.stdout or ""
            self._last_command_stderr = result.stderr or ""
            self._last_command_returncode = result.returncode
            return result.stdout
        except CommandTimeoutError:
            logging.info("Command timed out")
            self._last_command_stdout = ''
            self._last_command_stderr = 'Command timed out'
            self._last_command_returncode = -1
            return None

    def kill_iperf(self):
        """
        Kill Iperf.

        -------------------------
        It executes external commands via Python's subprocess module.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if self._is_performance_debug_enabled():
            logging.info("Database debug mode enabled, skip killing iperf processes")
            return
        commands = []

        # Kill iperf processes on the host (Windows/Linux PC).
        commands.append(pytest.dut.IPERF_KILL.format(self.test_tool))
        commands.append(pytest.dut.IPERF_WIN_KILL.format(self.test_tool))

        # Also attempt to kill iperf on the DUT side via ADB when applicable.
        connect_type = str(getattr(pytest, "connect_type", "")).lower()
        serial = getattr(self, "serialnumber", "") or getattr(pytest, "serialnumber", "")
        if connect_type == "android" and serial:
            # Best‑effort; device might not have killall/pkill, errors are ignored by _run_host_commands.
            commands.append(f'adb -s {serial} shell killall -9 {self.test_tool}')
            commands.append(f'adb -s {serial} shell pkill -9 {self.test_tool}')

        self._run_host_commands(commands)

    def _run_host_commands(self, commands: Sequence[str]) -> None:
        """Execute a sequence of host commands while swallowing non-critical failures."""
        batch = CommandBatch(self.command_runner)
        for cmd in commands:
            batch.add(cmd, shell=True, ignore_error=True)
        try:
            batch.run()
        except CommandExecutionError:
            logging.debug("Host command batch reported an execution error", exc_info=True)
        except CommandTimeoutError:
            logging.debug("Host command batch reported a timeout", exc_info=True)

    def push_iperf(self):
        """
        Push Iperf.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if pytest.connect_type == 'Linux':
            return
        if self.checkoutput('[ -e /system/bin/iperf ] && echo yes || echo no').strip() != 'yes':
            path = os.path.join(os.getcwd(), 'res/iperf')
            self.push(path, '/system/bin')
            self.checkoutput('chmod a+x /system/bin/iperf')

    def run_iperf(self, command, adb):
        """
        Run Iperf.

        -------------------------
        It executes external commands via Python's subprocess module.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        command : Any
            The ``command`` parameter.
        adb : Any
            The ``adb`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        encoding = 'gbk' if pytest.win_flag else 'utf-8'
        use_adb = bool(adb)
        self._current_udp_mode = self._is_udp_command(command)

        def _extend_logs(target_list: list[str], lines, label: str | None = None):
            """
            Extend logs.

            -------------------------
            It logs information for debugging or monitoring purposes.

            -------------------------
            Parameters
            -------------------------
            target_list : Any
                The ``target_list`` parameter.
            lines : Any
                The ``lines`` parameter.
            label : Any
                The ``label`` parameter.

            -------------------------
            Returns
            -------------------------
            None
                This method does not return a value.
            """
            if not lines:
                return
            if isinstance(lines, str):
                iterable = lines.splitlines()
            else:
                iterable = lines
            for line in iterable:
                if line is None:
                    continue
                text = line.rstrip('\r\n') if isinstance(line, str) else str(line)
                if text:
                    target_list.append(text)
                    if label:
                        logging.info("%s %s", label, text)

        def _read_output(proc, stream, target_list: list[str], label: str):
            """
            Read output.

            -------------------------
            It logs information for debugging or monitoring purposes.

            -------------------------
            Parameters
            -------------------------
            proc : Any
                The ``proc`` parameter.
            stream : Any
                The ``stream`` parameter.
            target_list : Any
                The ``target_list`` parameter.
            label : Any
                The ``label`` parameter.

            -------------------------
            Returns
            -------------------------
            None
                This method does not return a value.
            """
            if not stream:
                logging.info("iperf stream reader thread (%s) exiting: no stream", label)
                return
            logging.info(
                "iperf stream reader thread started (%s pid=%s)",
                label,
                getattr(proc, "pid", None),
            )
            try:
                with stream:
                    for line in iter(stream.readline, ''):
                        if line:
                            _extend_logs(target_list, [line], label)
            except Exception:
                logging.exception("iperf stream reader thread (%s) hit an exception", label)
            finally:
                logging.info(
                    "iperf stream reader thread finished (%s pid=%s)",
                    label,
                    getattr(proc, "pid", None),
                )

        def _start_background(cmd_list, desc):
            """
            Start background.

            -------------------------
            It executes external commands via Python's subprocess module.
            It logs information for debugging or monitoring purposes.

            -------------------------
            Parameters
            -------------------------
            cmd_list : Any
                The ``cmd_list`` parameter.
            desc : Any
                The ``desc`` parameter.

            -------------------------
            Returns
            -------------------------
            Any
                The result produced by the function.
            """
            logging.debug('%s %s', desc, command)
            logging.debug("command list: %s", cmd_list)
            process = self.command_runner.popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding=encoding,
            )
            logging.debug(
                "background process started (%s pid=%s)",
                desc,
                getattr(process, "pid", None),
            )
            Thread(target=_read_output,
                   args=(process, process.stdout, self.iperf_server_log_list, "iperf server stdout:"),
                   daemon=True).start()
            Thread(target=_read_output,
                   args=(process, process.stderr, self.iperf_server_log_list, "iperf server stderr:"),
                   daemon=True).start()
            return process

        def _run_blocking(cmd_list, desc):
            """
            Run blocking.

            -------------------------
            It executes external commands via Python's subprocess module.
            It logs information for debugging or monitoring purposes.

            -------------------------
            Parameters
            -------------------------
            cmd_list : Any
                The ``cmd_list`` parameter.
            desc : Any
                The ``desc`` parameter.

            -------------------------
            Returns
            -------------------------
            None
                This method does not return a value.
            """
            logging.info('%s %s', desc, command)
            logging.info("command list: %s", cmd_list)
            process = self.command_runner.popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding=encoding,
            )
            logging.info(
                "blocking process started (%s pid=%s)", desc, getattr(process, "pid", None)
            )

            def _collect_output(stdout_text: str | None, stderr_text: str | None) -> None:
                """
                Collect output.

                -------------------------
                It logs information for debugging or monitoring purposes.

                -------------------------
                Parameters
                -------------------------
                stdout_text : Any
                    The ``stdout_text`` parameter.
                stderr_text : Any
                    The ``stderr_text`` parameter.

                -------------------------
                Returns
                -------------------------
                None
                    A value of type ``None``.
                """
                if stderr_text:
                    logging.warning(stderr_text.strip())
                if stdout_text:
                    logging.debug(stdout_text.strip())

            try:
                stdout, stderr = process.communicate(timeout=self.iperf_wait_time)
                _collect_output(stdout, stderr)
            except subprocess.TimeoutExpired:
                logging.warning(f'{desc} timeout after {self.iperf_wait_time}s')
                process.kill()
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except Exception:
                    logging.debug('Failed to collect iperf output after timeout', exc_info=True)
                else:
                    _collect_output(stdout, stderr)
            finally:
                logging.info(
                    "%s process return code: %s",
                    desc,
                    process.returncode,
                )

        def _build_cmd_list():
            """
            Build cmd list.

            -------------------------
            Returns
            -------------------------
            Any
                The result produced by the function.
            """
            if use_adb and pytest.connect_type != 'Linux':
                return ['adb', '-s', self.serialnumber, 'shell', *command.split()]
            return command.split()

        if '-s' in command:
            self.iperf_server_log_list = []
            if use_adb:
                if pytest.connect_type == 'Linux':
                    def telnet_iperf():
                        """
                        Telnet Iperf.

                        -------------------------
                        It logs information for debugging or monitoring purposes.

                        -------------------------
                        Returns
                        -------------------------
                        None
                            This method does not return a value.
                        """
                        logging.info(f'server telnet command: {command}')
                        tn = telnetlib.Telnet(self.dut_ip)
                        tn.write(command.encode('ascii') + b'\n')
                        try:
                            while True:
                                line = tn.read_until(b'\n', timeout=1).decode('gbk', 'ignore').strip()
                                if line:
                                    _extend_logs(self.iperf_server_log_list, [line], "iperf server telnet:")
                        except EOFError:
                            logging.info('telnet server session closed')
                        finally:
                            tn.close()

                    t = Thread(target=telnet_iperf, daemon=True)
                    t.start()
                    return None
                else:
                    return _start_background(_build_cmd_list(), 'server adb command:')
            else:
                return _start_background(_build_cmd_list(), 'server pc command:')
        else:
            if use_adb:
                if pytest.connect_type == 'Linux':
                    logging.info(f'client telnet command: {command}')

                    async def _run_telnet_client():
                        """
                        Run telnet client.

                        -------------------------
                        Returns
                        -------------------------
                        None
                            This method does not return a value.
                        """
                        await asyncio.wait_for(self.telnet_client(command), timeout=self.iperf_wait_time)

                    try:
                        asyncio.run(_run_telnet_client())
                    except asyncio.TimeoutError:
                        logging.warning(f'client telnet command timeout after {self.iperf_wait_time}s')
                else:
                    _run_blocking(_build_cmd_list(), 'client adb command:')
            else:
                _run_blocking(_build_cmd_list(), 'client pc command:')

    def _parse_iperf_log(self, server_lines: list[str]):
        """
        Parse Iperf log.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        server_lines : Any
            The ``server_lines`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """

        def _analyse_lines(lines: list[str]) -> tuple[Optional[float], Optional[IperfMetrics], int, bool]:
            """
            Analyse lines.

            -------------------------
            It logs information for debugging or monitoring purposes.

            -------------------------
            Parameters
            -------------------------
            lines : Any
                The ``lines`` parameter.

            -------------------------
            Returns
            -------------------------
            tuple[Optional[float], Optional[IperfMetrics], int, bool]
                A value of type ``tuple[Optional[float], Optional[IperfMetrics], int, bool]``.
            """
            interval_pattern = re.compile(r'(\d+(?:\.\d*)?)\s*-\s*(\d+(?:\.\d*)?)\s*sec', re.IGNORECASE)
            values: list[float] = []
            seen_intervals: set[tuple[str, str]] = set()
            udp_metrics_local: Optional[IperfMetrics] = None
            summary_value: Optional[float] = None
            has_summary_line = False

            for raw_line in lines:
                line = dut._sanitize_iperf_line(raw_line)
                if not line:
                    continue
                if '[SUM]' not in line and self.pair != 1:
                    metrics = self._extract_udp_metrics(line)
                    if metrics:
                        udp_metrics_local = metrics
                        self._current_udp_mode = True
                    continue
                metrics = self._extract_udp_metrics(line)
                if metrics:
                    udp_metrics_local = metrics
                    self._current_udp_mode = True
                interval_match = interval_pattern.search(line)
                if not interval_match:
                    continue
                interval_key = (interval_match.group(1), interval_match.group(2))
                try:
                    start_time = float(interval_match.group(1))
                    end_time = float(interval_match.group(2))
                except (TypeError, ValueError):
                    start_time = end_time = 0.0
                bandwidth_match = re.search(r'(\d+(?:\.\d+)?)\s*([KMG]?bits/sec)', line, re.IGNORECASE)
                if not bandwidth_match:
                    continue
                throughput = self._convert_bandwidth_to_mbps(
                    float(bandwidth_match.group(1)), bandwidth_match.group(2)
                )
                if throughput is None:
                    continue
                if interval_key in seen_intervals:
                    logging.debug(f'skip duplicate interval {interval_key} (throughput={throughput})')
                    continue
                seen_intervals.add(interval_key)
                values.append(throughput)
                duration = end_time - start_time
                if start_time < 0.5 and duration > 1.5:
                    summary_value = throughput
                    has_summary_line = True

            if summary_value is not None:
                throughput_value = summary_value
            elif values:
                logging.info(f'[coco] {values}')
                logging.info(f'[coco] {len(values)}')
                throughput_value = sum(values) / len(values)
            elif udp_metrics_local and udp_metrics_local.throughput_mbps is not None:
                throughput_value = udp_metrics_local.throughput_mbps
            else:
                throughput_value = None

            return throughput_value, udp_metrics_local, len(values), has_summary_line

        server_value, server_udp_metrics, server_count, server_has_summary = _analyse_lines(server_lines)

        preferred_value = server_value
        preferred_udp = server_udp_metrics

        line_count = server_count
        expected_intervals_raw = getattr(self, "iperf_test_time", 0) or 0
        expected_intervals = int(expected_intervals_raw) if expected_intervals_raw else 0
        if not server_has_summary:
            if line_count:
                if expected_intervals and line_count < expected_intervals:
                    logging.warning(
                        "iperf output only produced %d intervals (expected %d)",
                        line_count,
                        expected_intervals,
                    )
                elif expected_intervals:
                    logging.info(
                        "iperf summary line missing; using average throughput over %d intervals",
                        line_count,
                    )
            else:
                logging.warning("iperf output did not contain interval lines")
        throughput_result = preferred_value if preferred_value is not None else None
        logging.info(
            "iperf throughput result after analysis: %s (intervals=%d, summary=%s)",
            throughput_result,
            line_count,
            server_has_summary,
        )

        if preferred_udp:
            preferred_udp.throughput_mbps = throughput_result
            return preferred_udp

        return IperfMetrics(throughput_result)

    def get_logcat(self):
        """
        Retrieve logcat.

        -------------------------
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        expected_intervals_raw = getattr(self, "iperf_test_time", 0) or 0
        expected_intervals = int(expected_intervals_raw) if expected_intervals_raw else 0
        if expected_intervals:
            interval_pattern = re.compile(r'(\d+(?:\.\d*)?)\s*-\s*(\d+(?:\.\d*)?)\s*sec', re.IGNORECASE)
            wait_deadline = time.time() + min(5.0, max(1.0, expected_intervals * 0.1))
            start_time = time.time()
            last_sum_count = -1
            last_total_lines = -1
            exit_reason = "deadline"
            has_summary = False
            while time.time() < wait_deadline:
                snapshot = list(self.iperf_server_log_list)
                total_lines = len(snapshot)
                sum_intervals: set[tuple[str, str]] = set()
                for text in snapshot:
                    sanitized = dut._sanitize_iperf_line(text)
                    if not sanitized:
                        continue
                    match = interval_pattern.search(sanitized)
                    if not match:
                        continue
                    start, end = match.group(1), match.group(2)
                    if '[SUM]' not in sanitized:
                        continue
                    sum_intervals.add((start, end))
                    if not has_summary:
                        try:
                            start_f = float(start)
                            end_f = float(end)
                        except (TypeError, ValueError):
                            continue
                        if end_f - start_f >= max(1.0, expected_intervals - 1):
                            has_summary = True
                current_sum_count = len(sum_intervals)
                elapsed = time.time() - start_time
                if (
                        current_sum_count != last_sum_count
                        or total_lines != last_total_lines
                ):
                    logging.debug(
                        "iperf wait: SUM intervals=%d total_lines=%d after %.2fs",
                        current_sum_count,
                        total_lines,
                        elapsed,
                    )
                    last_sum_count = current_sum_count
                    last_total_lines = total_lines
                if has_summary:
                    exit_reason = "summary_line"
                    break
                if expected_intervals and current_sum_count >= expected_intervals:
                    exit_reason = "expected_interval_count"
                    break
                time.sleep(0.1)
            elapsed = time.time() - start_time
            logging.debug(
                "iperf wait finished: sum_intervals=%d, summary=%s, elapsed=%.2fs, reason=%s",
                last_sum_count if last_sum_count >= 0 else 0,
                has_summary,
                elapsed,
                exit_reason,
            )
        server_lines = list(self.iperf_server_log_list)
        logging.debug("iperf server raw lines captured: %d", len(server_lines))
        if not server_lines:
            logging.debug(
                "iperf server log list is empty; background reader may not have received data yet"
            )
        else:
            preview_count = min(5, len(server_lines))
            logging.debug(
                "iperf server log preview (first %d lines): %s",
                preview_count,
                server_lines[:preview_count],
            )
        result = self._parse_iperf_log(server_lines)
        self.iperf_server_log_list.clear()
        if result is None:
            return None
        if result.throughput_mbps is not None:
            result.throughput_mbps = round(result.throughput_mbps, 1)
        if result.latency_ms is not None:
            result.latency_ms = round(result.latency_ms, 3)
        return result

    def get_pc_ip(self):
        """
        Retrieve pc ip.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if pytest.win_flag:
            ipfoncig_info = pytest.dut.checkoutput_term('ipconfig').strip()
            pc_ip = re.findall(r'IPv4.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
        else:
            ipfoncig_info = pytest.dut.checkoutput_term('ifconfig')
            pc_ip = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
        if not pc_ip: assert False, "Can't get pc ip"
        return pc_ip

    def get_dut_ip(self):
        """
        Retrieve dut ip.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if pytest.connect_type == 'Linux':
            return pytest.dut.dut_ip
        dut_info = pytest.dut.checkoutput('ifconfig wlan0')
        dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)
        if dut_ip:
            dut_ip = dut_ip[0]
        if not dut_ip: assert False, "Can't get dut ip"
        return dut_ip

    @step
    def get_rx_rate(self, router_info, type='TCP', corner_tool=None, db_set='', debug=False):
        """
        Retrieve rx rate.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        router_info : Any
            The ``router_info`` parameter.
        type : Any
            Type specifier for the UI automation tool (e.g., "u2").
        corner_tool : Any
            The ``corner_tool`` parameter.
        db_set : Any
            The ``db_set`` parameter.
        debug : Any
            The ``debug`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        router_cfg = {
            router_info.band: {
                'mode': router_info.wireless_mode,
                'security_mode': router_info.security_mode,
                'bandwidth': router_info.bandwidth,
            }
        }
        chip_info = getattr(pytest, "chip_info", None)
        expect_rate = handle_expectdata(router_cfg, router_info.band, 'DL', chip_info)
        if self.skip_rx:
            corner = corner_tool.get_turntanle_current_angle() if corner_tool else ''
            throughput_cells = self._normalize_throughput_cells(['0'])
            values = self._build_throughput_result_values(
                router_info,
                type,
                'DL',
                db_set,
                corner,
                None,
                throughput_cells,
                expect_rate,
                None,
                None,
            )
            self._ensure_performance_result()
            pytest.testResult.save_result(self._format_result_row(values))
            return 'N/A'

        rx_metrics_list: list[IperfMetrics] = []
        self.rvr_result = None
        mcs_rx = None

        database_debug = self._is_performance_debug_enabled()
        debug_enabled = debug or database_debug
        if debug_enabled:
            sources = []
            if debug:
                sources.append("parameter")
            if database_debug:
                sources.append("database flag")
            reason = " + ".join(sources) if sources else "unknown"
            simulated = round(random.uniform(100, 200), 2)
            logging.info(
                "Debug throughput mode enabled (%s), skip iperf RX test and return %.2f Mbps",
                reason,
                simulated,
            )
            rx_metrics_list.append(IperfMetrics(simulated))
            mcs_rx = "DEBUG"
        else:
            for c in range(self.repest_times + 1):
                logging.info(f'run rx {c} loop')
                rx_result = 0
                mcs_rx = 0
                if self.rvr_tool == 'iperf':
                    pytest.dut.kill_iperf()
                    terminal = pytest.dut.run_iperf(self.tool_path + pytest.dut.iperf_server_cmd, self.serialnumber)
                    time.sleep(1)
                    client_cmd = pytest.dut.iperf_client_cmd.replace('{ip}', self.dut_ip)
                    pytest.dut.run_iperf(client_cmd, '')
                    if pytest.connect_type == 'Linux':
                        time.sleep(5)
                    rx_result = self.get_logcat()
                    self.rvr_result = None
                    if terminal and hasattr(terminal, 'terminate'):
                        try:
                            terminal.terminate()
                        except Exception as e:
                            logging.warning(f'Fail to kill run_iperf terminal \n {e}')
                elif self.rvr_tool == 'ixchariot':
                    ix.ep1 = self.pc_ip
                    ix.ep2 = self.dut_ip
                    ix.pair = self.pair
                    rx_result = ix.run_rvr()

                if rx_result == False:
                    logging.info("Connect failed")
                    if self.rvr_tool == 'ixchariot':
                        pytest.dut.checkoutput(pytest.dut.STOP_IX_ENDPOINT_COMMAND)
                        time.sleep(1)
                        pytest.dut.checkoutput(pytest.dut.IX_ENDPOINT_COMMAND)
                        time.sleep(3)
                    continue

                time.sleep(3)
                if isinstance(rx_result, IperfMetrics):
                    metrics = rx_result
                else:
                    try:
                        throughput = float(rx_result) if rx_result is not None else None
                    except Exception:
                        throughput = None
                    metrics = IperfMetrics(throughput)
                logging.info(f'rx result {metrics}')
                mcs_rx = pytest.dut.get_mcs_rx()
                logging.info(f'{metrics}, {mcs_rx}')
                rx_metrics_list.append(metrics)
                if len(rx_metrics_list) > self.repest_times:
                    break

        if rx_metrics_list:
            try:
                first = rx_metrics_list[0].throughput_mbps
                rx_val = float(first) if first is not None else 0
            except Exception:
                rx_val = 0
            if rx_val < self.throughput_threshold:
                self.skip_rx = True

        throughput_entries: list[str] = []
        for metric in rx_metrics_list:
            formatted = metric.formatted_throughput()
            if formatted is not None:
                throughput_entries.append(formatted)
        throughput_cells = self._normalize_throughput_cells(throughput_entries)
        latency_value = rx_metrics_list[-1].latency_ms if rx_metrics_list else None
        packet_loss_value = rx_metrics_list[-1].packet_loss if rx_metrics_list else None
        corner = corner_tool.get_turntanle_current_angle() if corner_tool else ''
        values = self._build_throughput_result_values(
            router_info,
            type,
            'DL',
            db_set,
            corner,
            mcs_rx,
            throughput_cells,
            expect_rate,
            latency_value,
            packet_loss_value,
        )
        self._ensure_performance_result()
        pytest.testResult.save_result(self._format_result_row(values))
        return ','.join([cell for cell in throughput_cells if cell]) or 'N/A'

    @step
    def get_tx_rate(self, router_info, type='TCP', corner_tool=None, db_set='', debug=False):
        """
        Retrieve tx rate.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        router_info : Any
            The ``router_info`` parameter.
        type : Any
            Type specifier for the UI automation tool (e.g., "u2").
        corner_tool : Any
            The ``corner_tool`` parameter.
        db_set : Any
            The ``db_set`` parameter.
        debug : Any
            The ``debug`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        router_cfg = {
            router_info.band: {
                'mode': router_info.wireless_mode,
                'security_mode': router_info.security_mode,
                'bandwidth': router_info.bandwidth,
            }
        }
        chip_info = getattr(pytest, "chip_info", None)
        expect_rate = handle_expectdata(router_cfg, router_info.band, 'UL', chip_info)
        if self.skip_tx:
            corner = corner_tool.get_turntanle_current_angle() if corner_tool else ''
            throughput_cells = self._normalize_throughput_cells(['0'])
            values = self._build_throughput_result_values(
                router_info,
                type,
                'UL',
                db_set,
                corner,
                None,
                throughput_cells,
                expect_rate,
                None,
                None,
            )
            formatted = self._format_result_row(values)
            logging.info(formatted)
            pytest.testResult.save_result(formatted)
            return 'N/A'

        tx_metrics_list: list[IperfMetrics] = []
        self.rvr_result = None
        mcs_tx = None

        database_debug = self._is_performance_debug_enabled()
        debug_enabled = debug or database_debug
        if debug_enabled:
            sources = []
            if debug:
                sources.append("parameter")
            if database_debug:
                sources.append("database flag")
            reason = " + ".join(sources) if sources else "unknown"
            simulated = round(random.uniform(100, 200), 2)
            logging.info(
                "Debug throughput mode enabled (%s), skip iperf TX test and return %.2f Mbps",
                reason,
                simulated,
            )
            tx_metrics_list.append(IperfMetrics(simulated))
            mcs_tx = "DEBUG"
        else:
            for c in range(self.repest_times + 1):
                logging.info(f'run tx:  {c} loop ')
                tx_result = 0
                mcs_tx = 0
                if self.rvr_tool == 'iperf':
                    pytest.dut.kill_iperf()
                    time.sleep(1)
                    terminal = pytest.dut.run_iperf(pytest.dut.iperf_server_cmd, '')
                    time.sleep(1)
                    client_cmd = pytest.dut.iperf_client_cmd.replace('{ip}', self.pc_ip)
                    pytest.dut.run_iperf(self.tool_path + client_cmd, self.serialnumber)
                    if pytest.connect_type == 'Linux':
                        time.sleep(5)
                    time.sleep(3)
                    tx_result = self.get_logcat()
                    self.rvr_result = None
                    if terminal and hasattr(terminal, 'terminate'):
                        try:
                            terminal.terminate()
                        except Exception as e:
                            logging.warning(f'Fail to kill run_iperf terminal \n {e}')
                elif self.rvr_tool == 'ixchariot':
                    ix.ep1 = self.dut_ip
                    ix.ep2 = self.pc_ip
                    ix.pair = self.pair
                    tx_result = ix.run_rvr()

                if tx_result == False:
                    logging.info("Connect failed")
                    if self.rvr_tool == 'ixchariot':
                        pytest.dut.checkoutput(pytest.dut.STOP_IX_ENDPOINT_COMMAND)
                        time.sleep(1)
                        pytest.dut.checkoutput(pytest.dut.IX_ENDPOINT_COMMAND)
                        time.sleep(3)
                    continue

                mcs_tx = pytest.dut.get_mcs_tx()
                if isinstance(tx_result, IperfMetrics):
                    metrics = tx_result
                else:
                    try:
                        throughput = float(tx_result) if tx_result is not None else None
                    except Exception:
                        throughput = None
                    metrics = IperfMetrics(throughput)
                logging.info(f'tx result {metrics}')
                logging.info(f'{metrics}, {mcs_tx}')
                tx_metrics_list.append(metrics)
                if len(tx_metrics_list) > self.repest_times:
                    break

        if tx_metrics_list:
            try:
                first = tx_metrics_list[0].throughput_mbps
                tx_val = float(first) if first is not None else 0
            except Exception:
                tx_val = 0
            if tx_val < self.throughput_threshold:
                self.skip_tx = True

        throughput_entries = []
        for metric in tx_metrics_list:
            formatted = metric.formatted_throughput()
            if formatted is not None:
                throughput_entries.append(formatted)
        throughput_cells = self._normalize_throughput_cells(throughput_entries)
        latency_value = tx_metrics_list[-1].latency_ms if tx_metrics_list else None
        packet_loss_value = tx_metrics_list[-1].packet_loss if tx_metrics_list else None
        corner = corner_tool.get_turntanle_current_angle() if corner_tool else ''
        values = self._build_throughput_result_values(
            router_info,
            type,
            'UL',
            db_set,
            corner,
            mcs_tx,
            throughput_cells,
            expect_rate,
            latency_value,
            packet_loss_value,
        )
        formatted = self._format_result_row(values)
        logging.info(formatted)
        self._ensure_performance_result()
        pytest.testResult.save_result(formatted)
        return ','.join([cell for cell in throughput_cells if cell]) or 'N/A'

    def wait_for_wifi_address(self, cmd: str = '', target='.', lan=True):
        """
        Wait for for Wi‑Fi address.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        cmd : Any
            Command string to parse or execute.
        target : Any
            The ``target`` parameter.
        lan : Any
            The ``lan`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if pytest.connect_type == 'Linux':
            pytest.dut.roku.ser.write('iw wlan0 link')
            logging.info(pytest.dut.roku.ser.recv())
            return True, pytest.dut.roku.ser.get_ip_address('wlan0')
        else:
            if lan and (not target):
                if not self.ip_target:
                    _ = self.pc_ip
                target = self.ip_target
            step = 0
            while True:
                time.sleep(3)
                step += 1
                info = self.checkoutput('ifconfig wlan0')
                ip_address = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', info, re.S)
                if ip_address:
                    ip_address = ip_address[0]
                if target in ip_address:
                    self.dut_ip = ip_address
                    break
                if step % 3 == 0:
                    logging.info('repeat command')
                    if cmd:
                        info = self.checkoutput(cmd)
                if step > 6:
                    assert False, f"Can't catch the address:{target} "
            logging.info(f'ip address {ip_address}')
            return True, ip_address

    def forget_wifi(self):
        """
        Forget Wi‑Fi.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if pytest.connect_type == 'Linux':
            ...
        else:
            list_networks_cmd = "cmd wifi list-networks"
            output = self.checkoutput(list_networks_cmd)
            if "No networks" in output:
                logging.debug("has no wifi connect")
            else:
                network_id = re.findall("\n(.*?) ", output)
                if network_id:
                    forget_wifi_cmd = "cmd wifi forget-network {}".format(int(network_id[0]))
                    output1 = self.checkoutput(forget_wifi_cmd)
                    if "successful" in output1:
                        logging.info(f"Network id {network_id[0]} closed")

    def wifi_scan(self, ssid):
        """
        Wi‑Fi scan.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        ssid : Any
            The ``ssid`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if pytest.connect_type == 'Linux':
            return pytest.dut.roku.wifi_scan(ssid)
        else:
            for _ in range(10):
                info = pytest.dut.checkoutput("cmd wifi start-scan;sleep 10;cmd wifi list-scan-results")
                logging.info(info)
                if ssid in info:
                    return True
                time.sleep(1)
            else:
                return False

    def connect_wifi(self, ssid: str, pwd: str, security: str, hide: bool = False, lan=True) -> bool:
        """
        Connect Wi‑Fi.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        ssid : Any
            The ``ssid`` parameter.
        pwd : Any
            The ``pwd`` parameter.
        security : Any
            The ``security`` parameter.
        hide : Any
            The ``hide`` parameter.
        lan : Any
            The ``lan`` parameter.

        -------------------------
        Returns
        -------------------------
        bool
            A value of type ``bool``.
        """

        connect_type = getattr(pytest, "connect_type", "").lower()
        if connect_type == "linux":
            try:
                self.wait_reconnect_sync(timeout=90)
                return True
            except Exception as exc:  # pragma: no cover - hardware dependent
                logging.info(exc)
                return False

        if connect_type == "android":
            return bool(self._android_connect_wifi(ssid, pwd, security, hide, lan))

        logging.error("Unsupported connect_type for connect_wifi: %s", connect_type)
        return False

    def connect_ssid(self, router=""):
        """
        Connect ssid.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Parameters
        -------------------------
        router : Any
            The ``router`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if pytest.connect_type == 'Linux':
            pytest.dut.roku.wifi_conn(ssid=router.ssid, pwd=router.password)
        else:
            pytest.dut.checkoutput(pytest.dut.get_wifi_cmd(router))

    @step
    def get_rssi(self):
        """
        Retrieve rssi.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if self._is_performance_debug_enabled():
            simulated_rssi = -random.randint(40, 80)
            self.rssi_num = simulated_rssi
            self.freq_num = 0
            logging.info(
                "Database debug mode enabled, skip real RSSI query and return simulated %s dBm",
                simulated_rssi,
            )
            return self.rssi_num
        for i in range(3):
            time.sleep(3)
            rssi_info = pytest.dut.checkoutput(pytest.dut.IW_LINNK_COMMAND)
            logging.info(f'Get WiFi link status via command {rssi_info}')
            if 'signal' in rssi_info:
                break
        else:
            rssi_info = ''

        if 'Not connected' in rssi_info:
            self.rssi_num = -1
            assert False, "Wifi is not connected"
        try:
            self.rssi_num = int(re.findall(r'signal:\s*(-?\d+)\s+dBm', rssi_info, re.S)[0])
            self.freq_num = int(re.findall(r'freq:\s+(\d+)\s+', rssi_info, re.S)[0])
        except IndexError as e:
            self.rssi_num = -1
            self.freq_num = -1
        return self.rssi_num

    step = staticmethod(step)
