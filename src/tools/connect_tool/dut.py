#!/usr/bin/env python 
# -*- coding: utf-8 -*- 


"""
# File       : dut.py
# Time       ：2023/7/4 15:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""
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

lock = threading.Lock()


@dataclass
class IperfMetrics:
    throughput_mbps: Optional[float]
    latency_ms: Optional[float] = None
    packet_loss: Optional[str] = None

    def formatted_throughput(self) -> Optional[str]:
        if self.throughput_mbps is None:
            return None
        return f"{self.throughput_mbps:.1f}"


class dut():
    count = 0
    DMESG_COMMAND = 'dmesg -S'
    CLEAR_DMESG_COMMAND = 'dmesg -c'

    SETTING_ACTIVITY_TUPLE = 'com.android.tv.settings', '.MainSettings'
    MORE_SETTING_ACTIVITY_TUPLE = 'com.droidlogic.tv.settings', '.more.MorePrefFragmentActivity'

    SKIP_OOBE = "pm disable com.google.android.tungsten.setupwraith;settings put secure user_setup_complete 1;settings put global device_provisioned 1;settings put secure tv_user_setup_complete 1"
    # iperf 相关命令
    IPERF_KILL = 'killall -9 {}'
    IPERF_WIN_KILL = 'taskkill /im {}.exe -f'

    @staticmethod
    def _parse_iperf_params(cmd: str) -> tuple[int, int]:
        t_match = re.search(r'-t\s+(\d+)', cmd)
        p_match = re.search(r'-P\s+(\d+)', cmd)
        test_time = int(t_match.group(1)) if t_match else 30
        pair = int(p_match.group(1)) if p_match else 1
        return test_time, pair

    @staticmethod
    def _is_udp_command(cmd: str) -> bool:
        return bool(re.search(r'(^|\s)-u(\s|$)', cmd))

    @staticmethod
    def _convert_bandwidth_to_mbps(value: float, unit: str) -> Optional[float]:
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
        if not text:
            return ""
        # 去除控制字符与 ANSI 转义序列，避免影响正则匹配
        without_ansi = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', text)
        cleaned = re.sub(r'[\x00-\x1f\x7f]', '', without_ansi)
        return cleaned.strip()

    @staticmethod
    def _extract_udp_metrics(line: str) -> Optional[IperfMetrics]:
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
        # {'link': '9Auq9mYxFEE', 'name': 'Sky Live'},
        {'link': '-ZMVjKT3-5A', 'name': 'NBC News (vp9)'},  # vp9
        {'link': 'LXb3EKWsInQ', 'name': 'COSTA RICA IN 4K 60fps HDR (ULTRA HD) (vp9)'},  # vp9
        {'link': 'b6fzbyPoNXY', 'name': 'Las Vegas Strip at Night in 4k UHD HLG HDR (vp9)'},  # vp9
        {'link': 'AtZrf_TWmSc', 'name': 'How to Convert,Import,and Edit AVCHD Files for Premiere (H264)'},  # H264
        {'link': 'LXb3EKWsInQ', 'name': 'COSTA RICA IN 4K 60fps HDR(ultra hd) (4k 60fps)'},  # 4k 60fps
        {'link': 'NVhmq-pB_cs', 'name': 'Mr Bean 720 25fps (720 25fps)'},
        {'link': 'bcOgjyHb_5Y', 'name': 'paid video'},
        {'link': 'rf7ft8-nUQQ', 'name': 'stress video'}
        # {'link': 'hNAbQYU0wpg', 'name': 'VR 360 Video of Top 5 Roller (360)'}  # 360
    ]

    WIFI_BUTTON_TAG = 'Available networks'

    def __init__(self):
        self.serialnumber = 'executer'
        cfg = load_config(refresh=True)
        rvr_cfg = cfg.get('rvr', {})
        self.rvr_tool = rvr_cfg.get('tool', 'iperf')
        iperf_cfg = rvr_cfg.get('iperf', {})
        self.iperf_server_cmd = iperf_cfg.get('server_cmd', 'iperf -s -w 2m -i 1')
        self.iperf_client_cmd = iperf_cfg.get('client_cmd', 'iperf -c {ip} -w 2m -i 1 -t 30 -P 5')
        self.iperf_test_time, self.pair = self._parse_iperf_params(self.iperf_client_cmd)
        self.iperf_wait_time = self.iperf_test_time + 5
        self.repest_times = int(rvr_cfg.get('repeat', 0))
        self._dut_ip = ''
        self._pc_ip = ''
        self.rvr_result = None
        self.throughput_threshold = float(rvr_cfg.get('throughput_threshold', 0))
        self.skip_tx = False
        self.skip_rx = False
        self.iperf_server_log_list: list[str] = []
        self.iperf_client_log_list: list[str] = []
        self._current_udp_mode = False
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
            self.ix.modify_tcl_script("set ixchariot_installation_dir ",
                                      f"set ixchariot_installation_dir \"{self.script_path}\"\n")

    @property
    def dut_ip(self):
        if self._dut_ip == '': self._dut_ip = self.get_dut_ip()
        return self._dut_ip

    @dut_ip.setter
    def dut_ip(self, value):
        self._dut_ip = value

    @property
    def pc_ip(self):
        if self._pc_ip == '': self._pc_ip = self.get_pc_ip()
        self.ip_target = '.'.join(self._pc_ip.split('.')[:3])
        return self._pc_ip

    @pc_ip.setter
    def pc_ip(self, value):
        self._pc_ip = value

    @property
    def freq_num(self):
        return self._freq_num

    @freq_num.setter
    def freq_num(self, value):
        self._freq_num = int(value)
        self.channel = int((self._freq_num - 2412) / 5 + 1 if self._freq_num < 3000 else (self._freq_num - 5000) / 5)

    @staticmethod
    def _format_result_row(values):
        def normalize(value: Optional[object]) -> str:
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
        def _first_token(text: str) -> str:
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
        total_runs = max(1, self.repest_times + 1)
        sanitized = entries[:total_runs]
        while len(sanitized) < total_runs:
            sanitized.append('')
        return [entry if entry is not None else '' for entry in sanitized]

    def step(func):
        def wrapper(*args, **kwargs):
            logging.info('-' * 80)
            dut.count += 1
            logging.info(f"Test Step {dut.count}:")
            logging.info(func.__name__)
            info = func(*args, **kwargs)

            logging.info('-' * 80)
            return info

        return wrapper

    def checkoutput_term(self, command):
        logging.info(f"command:{command}")
        try:
            result = subprocess.Popen(command, shell=True,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      encoding='gb2312' if pytest.win_flag else "utf-8",
                                      errors='ignore')
            # logging.info(f'{result.communicate()[0]}')
            return result.communicate()[0]
        except subprocess.TimeoutExpired:
            logging.info("Command timed out")
            return None

    def kill_iperf(self):
        if is_database_debug_enabled():
            logging.info("Database debug mode enabled, skip killing iperf processes")
            return
        try:
            pytest.dut.subprocess_run(pytest.dut.IPERF_KILL.format(self.test_tool))
        except Exception:
            ...

        try:
            pytest.dut.popen_term(pytest.dut.IPERF_KILL.format(self.test_tool))
        except Exception:
            ...
        # try:
        #     pytest.dut.subprocess_run(pytest.dut.IPERF_KILL.replace('iperf', 'iperf3'))
        #     pytest.dut.popen_term(pytest.dut.IPERF_KILL.replace('iperf', 'iperf3'))
        # except Exception:
        #     ...

        try:
            pytest.dut.popen_term(pytest.dut.IPERF_WIN_KILL.format(self.test_tool))
        except Exception:
            ...
        # try:
        #     pytest.dut.popen_term(pytest.dut.IPERF_WIN_KILL.replace('iperf', 'iperf3'))
        # except Exception:
        #     ...

    def push_iperf(self):
        if pytest.connect_type == 'telnet':
            return
        if self.checkoutput('[ -e /system/bin/iperf ] && echo yes || echo no').strip() != 'yes':
            path = os.path.join(os.getcwd(), 'res/iperf')
            self.push(path, '/system/bin')
            self.checkoutput('chmod a+x /system/bin/iperf')

    def run_iperf(self, command, adb):
        encoding = 'gbk' if pytest.win_flag else 'utf-8'
        use_adb = bool(adb)
        self._current_udp_mode = self._is_udp_command(command)

        def _extend_logs(target_list: list[str], lines):
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

        def _read_output(proc, target_list: list[str]):
            if not proc.stdout:
                return
            with proc.stdout:
                for line in iter(proc.stdout.readline, ''):
                    if line:
                        _extend_logs(target_list, [line])

        def _start_background(cmd_list, desc):
            logging.info(f'{desc} {command}')
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding=encoding,
                errors='ignore',
            )
            Thread(target=_read_output, args=(process, self.iperf_server_log_list), daemon=True).start()
            return process

        def _run_blocking(cmd_list, desc):
            logging.info(f'{desc} {command}')
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding=encoding,
                errors='ignore',
            )
            try:
                stdout, stderr = process.communicate(timeout=self.iperf_wait_time)
                if stderr:
                    logging.warning(stderr.strip())
                if stdout:
                    logging.debug(stdout.strip())
                    _extend_logs(self.iperf_client_log_list, stdout.splitlines())
            except subprocess.TimeoutExpired:
                logging.warning(f'{desc} timeout after {self.iperf_wait_time}s')
                process.kill()
                try:
                    process.communicate(timeout=2)
                except Exception:
                    ...

        def _build_cmd_list():
            if use_adb and pytest.connect_type != 'telnet':
                return ['adb', '-s', self.serialnumber, 'shell', *command.split()]
            return command.split()

        if '-s' in command:
            self.iperf_server_log_list = []
            self.iperf_client_log_list = []
            if use_adb:
                if pytest.connect_type == 'telnet':
                    def telnet_iperf():
                        logging.info(f'server telnet command: {command}')
                        tn = telnetlib.Telnet(self.dut_ip)
                        tn.write(command.encode('ascii') + b'\n')
                        try:
                            while True:
                                line = tn.read_until(b'\n', timeout=1).decode('gbk', 'ignore').strip()
                                if line:
                                    _extend_logs(self.iperf_server_log_list, [line])
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
                if pytest.connect_type == 'telnet':
                    logging.info(f'client telnet command: {command}')

                    async def _run_telnet_client():
                        output = await asyncio.wait_for(self.telnet_client(command), timeout=self.iperf_wait_time)
                        _extend_logs(self.iperf_client_log_list, output)

                    try:
                        asyncio.run(_run_telnet_client())
                    except asyncio.TimeoutError:
                        logging.warning(f'client telnet command timeout after {self.iperf_wait_time}s')
                else:
                    _run_blocking(_build_cmd_list(), 'client adb command:')
            else:
                _run_blocking(_build_cmd_list(), 'client pc command:')

    def _parse_iperf_log(self, lines):
        """解析 iperf 日志并计算吞吐量."""
        result_list: list[float] = []
        udp_metrics: Optional[IperfMetrics] = None
        interval_pattern = re.compile(r'\d+\.\d*\s*-\s*\d+\.\d*\s*sec', re.IGNORECASE)

        for raw_line in lines:
            line = dut._sanitize_iperf_line(raw_line)
            if not line:
                continue
            if '[SUM]' not in line and self.pair != 1:
                metrics = self._extract_udp_metrics(line)
                if metrics:
                    udp_metrics = metrics
                    self._current_udp_mode = True
                continue
            logging.info(f'line : {line}')
            metrics = self._extract_udp_metrics(line)
            if metrics:
                udp_metrics = metrics
                self._current_udp_mode = True
            if not interval_pattern.search(line):
                continue
            bandwidth_match = re.search(r'(\d+(?:\.\d+)?)\s*([KMG]?bits/sec)', line, re.IGNORECASE)
            if bandwidth_match:
                throughput = self._convert_bandwidth_to_mbps(
                    float(bandwidth_match.group(1)), bandwidth_match.group(2)
                )
                if throughput is not None:
                    result_list.append(throughput)

        if result_list:
            throughput_value = sum(result_list) / len(result_list)
        elif udp_metrics and udp_metrics.throughput_mbps is not None:
            throughput_value = udp_metrics.throughput_mbps
        else:
            throughput_value = 0.0

        if self.rssi_num > -60:
            throughput_result = throughput_value if throughput_value else None
        elif len(lines) > 30:
            throughput_result = throughput_value
        else:
            throughput_result = None

        if udp_metrics:
            udp_metrics.throughput_mbps = throughput_result
            return udp_metrics

        return IperfMetrics(throughput_result)

    def get_logcat(self):
        # pytest.dut.kill_iperf()
        # 分析 iperf 测试结果
        lines: list[str] = []
        if self.iperf_server_log_list:
            lines.extend(self.iperf_server_log_list)
        if self.iperf_client_log_list:
            lines.extend(self.iperf_client_log_list)
        result = self._parse_iperf_log(lines)
        self.iperf_server_log_list.clear()
        self.iperf_client_log_list.clear()
        if result is None:
            return None
        if result.throughput_mbps is not None:
            result.throughput_mbps = round(result.throughput_mbps, 1)
        if result.latency_ms is not None:
            result.latency_ms = round(result.latency_ms, 3)
        return result

    def get_pc_ip(self):
        if pytest.win_flag:
            ipfoncig_info = pytest.dut.checkoutput_term('ipconfig').strip()
            pc_ip = re.findall(r'IPv4.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
        else:
            ipfoncig_info = pytest.dut.checkoutput_term('ifconfig')
            pc_ip = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
        if not pc_ip: assert False, "Can't get pc ip"
        return pc_ip

    def get_dut_ip(self):
        if pytest.connect_type == 'telnet':
            return pytest.dut.dut_ip
        dut_info = pytest.dut.checkoutput('ifconfig wlan0')
        dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)
        if dut_ip:
            dut_ip = dut_ip[0]
        if not dut_ip: assert False, "Can't get dut ip"
        return dut_ip

    @step
    def get_rx_rate(self, router_info, type='TCP', corner_tool=None, db_set='', debug=False):
        router_cfg = {
            router_info.band: {
                'mode': router_info.wireless_mode,
                'security_mode': router_info.security_mode,
                'bandwidth': router_info.bandwidth,
            }
        }
        expect_rate = handle_expectdata(router_cfg, router_info.band, 'DL', pytest.chip_info)
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
            pytest.testResult.save_result(self._format_result_row(values))
            return 'N/A'

        rx_metrics_list: list[IperfMetrics] = []
        self.rvr_result = None
        mcs_rx = None

        database_debug = is_database_debug_enabled()
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
                    if pytest.connect_type == 'telnet':
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
        pytest.testResult.save_result(self._format_result_row(values))
        return ','.join([cell for cell in throughput_cells if cell]) or 'N/A'

    @step
    def get_tx_rate(self, router_info, type='TCP', corner_tool=None, db_set='', debug=False):
        router_cfg = {
            router_info.band: {
                'mode': router_info.wireless_mode,
                'security_mode': router_info.security_mode,
                'bandwidth': router_info.bandwidth,
            }
        }
        expect_rate = handle_expectdata(router_cfg, router_info.band, 'UL', pytest.chip_info)
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

        database_debug = is_database_debug_enabled()
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
                    if pytest.connect_type == 'telnet':
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
        pytest.testResult.save_result(formatted)
        return ','.join([cell for cell in throughput_cells if cell]) or 'N/A'

    def wait_for_wifi_address(self, cmd: str = '', target=''):
        if pytest.connect_type == 'telnet':
            pytest.dut.roku.ser.write('iw wlan0 link')
            logging.info(pytest.dut.roku.ser.recv())
            return True, pytest.dut.roku.ser.get_ip_address('wlan0')
        else:
            # Wait for th wireless adapter to obtaion the ip address
            if not target:
                target = self.ip_target
            logging.info(f"waiting for wifi {target}")
            step = 0
            while True:
                time.sleep(3)
                step += 1
                info = self.checkoutput('ifconfig wlan0')
                # logging.info(f'info {info}')
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
        '''
        Remove the network mentioned by <networkId>
        '''
        if pytest.connect_type == 'telnet':
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
        if pytest.connect_type == 'telnet':
            return pytest.dut.roku.wifi_scan(ssid)
        else:
            for _ in range(5):
                info = pytest.dut.checkoutput("cmd wifi start-scan;sleep 5;cmd wifi list-scan-results")
                logging.info(info)
                if ssid in info:
                    return True
                time.sleep(1)
            else:
                return False

    def connect_ssid(self, router=""):
        if pytest.connect_type == 'telnet':
            pytest.dut.roku.wifi_conn(ssid=router.ssid, pwd=router.wpa_passwd)
        else:
            pytest.dut.checkoutput(pytest.dut.get_wifi_cmd(router))

    @step
    def get_rssi(self):
        if is_database_debug_enabled():
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
            assert False, "Wifi is not connected"
        try:
            self.rssi_num = int(re.findall(r'signal:\s+-?(\d+)\s+dBm', rssi_info, re.S)[0])
            self.freq_num = int(re.findall(r'freq:\s+(\d+)\s+', rssi_info, re.S)[0])
        except IndexError as e:
            self.rssi_num = -1
            self.freq_num = -1
        return self.rssi_num

    step = staticmethod(step)
