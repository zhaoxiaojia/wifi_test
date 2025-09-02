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
import pytest
import telnetlib
from src.tools.ixchariot import ix
from threading import Thread
from src.tools.config_loader import load_config
from src.tools.router_tool.router_performance import handle_expectdata

lock = threading.Lock()


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
        p_match = re.search(r'-p\s+(\d+)', cmd)
        test_time = int(t_match.group(1)) if t_match else 30
        pair = int(p_match.group(1)) if p_match else 5
        return test_time, pair

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
        self.iperf_client_cmd = iperf_cfg.get('client_cmd', 'iperf -c {ip} -w 2m -i 1 -t 30 -p 5')
        self.iperf_test_time, self.pair = self._parse_iperf_params(self.iperf_client_cmd)
        logging.info(f'self.pair {self.pair}')
        self.iperf_wait_time = self.iperf_test_time + 5
        self.repest_times = int(rvr_cfg.get('repeat', 0))
        self._dut_ip = ''
        self._pc_ip = ''
        self.rvr_result = None
        self.throughput_threshold = float(rvr_cfg.get('throughput_threshold', 0))
        self.skip_tx = False
        self.skip_rx = False
        self.iperf_log_list: list[str] = []
        if self.rvr_tool == 'iperf':
            cmds = f"{self.iperf_server_cmd} {self.iperf_client_cmd}"
            self.test_tool = 'iperf3' if 'iperf3' in cmds else 'iperf'
            self.tool_path = iperf_cfg.get('path', '')
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
        def telnet_iperf():
            tn = telnetlib.Telnet(pytest.dut.dut_ip)
            logging.info(f'run thread: {command}')
            tn.write(command.encode('ascii') + b'\n')
            while True:
                line = tn.read_until(b'Mbits/sec').decode('gbk').strip()
                self.iperf_log_list.append(line)
                result = self._parse_iperf_log(self.iperf_log_list)
                if self.rssi_num > -60:
                    if result:
                        with lock:
                            self.rvr_result = result
                        break
                else:
                    if len(self.iperf_log_list) > 30:
                        with lock:
                            self.rvr_result = result if result else None
                        break
            logging.info('run thread done')
        if '-s' in command:
            self.iperf_log_list = []
        if '-s' in command:
            if adb:
                if pytest.connect_type == 'telnet':
                    t = Thread(target=telnet_iperf)
                    t.daemon = True
                    t.start()
                    return None
                else:
                    command = f'adb -s {pytest.dut.serialnumber} shell {command} '
                    logging.info(f'server adb command: {command}')
                    process = subprocess.Popen(
                        command.split(),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        encoding='utf-8',
                    )

                    def _read_output(proc):
                        for line in proc.stdout:
                            self.iperf_log_list.append(line)

                    Thread(target=_read_output, args=(process,), daemon=True).start()
                    return process
            else:
                logging.info(f'server pc command: {command}')
                process = subprocess.Popen(
                    command.split(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    encoding='utf-8',
                )

                def _read_output(proc):
                    for line in proc.stdout:
                        self.iperf_log_list.append(line)

                Thread(target=_read_output, args=(process,), daemon=True).start()
                return process
        else:
            if adb:
                async def run_adb_iperf():
                    # 定义命令和参数
                    # command = [
                    # 	'adb', '-s', pytest.dut.serialnumber, 'shell',
                    # 	'iperf', '-c',pytest.dut.pc_ip, '-w', '2m', '-i', '1', '-t',pytest.dut.IPERF_TEST_TIME, '-P5'
                    # ]

                    # 创建子进程
                    process = await asyncio.create_subprocess_exec(
                        *command.split(),  # 解包命令和参数
                        stdout=asyncio.subprocess.PIPE,  # 捕获标准输出
                        stderr=asyncio.subprocess.PIPE  # 捕获标准错误
                    )
                    try:
                        # 等待命令完成，设置超时时间（例如 40 秒）
                        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=35)
                        # print("Command output:", stdout.decode())  # 打印标准输出
                        if stderr:
                            logging.warning(f"Command error: {stderr.decode()}")  # 打印标准错误
                    except asyncio.TimeoutError:
                        logging.warning("Command timed out")
                        process.terminate()  # 终止进程
                        await process.wait()  # 等待进程完全终止

                logging.info(f'client adb command: {command}')
                if pytest.connect_type == 'telnet':
                    pytest.dut.checkoutput(command)
                else:
                    command = f'adb -s {pytest.dut.serialnumber} shell timeout 35 {command} '
                    # command = f'adb -s {pytest.dut.serialnumber} shell {command} '
                    logging.info(f'run over async {command}')
                    # 运行异步函数
                    asyncio.run(run_adb_iperf())
                    logging.info('run over async done')
            else:
                logging.info(f'client pc command: {command}')
                subprocess.Popen(command.split())

    def _parse_iperf_log(self, lines):
        """解析 iperf 日志并计算吞吐量."""
        result_list = []
        for line in lines:
            if '[SUM]' not in line and self.pair != 1:
                continue
            if line.strip():
                logging.info(f'line : {line.strip()}')
            data = re.findall(r'.*?\d+\.\d*-\s*\d+\.\d*.*?(\d+\.*\d*)\s+Mbits/sec.*?', line.strip(), re.S)
            if data:
                result_list.append(float(data[0]))
            data = re.findall('\s0\.0+-\s*3\d+\.\d*.*?(\d+\.*\d*)\s+Mbits/sec.*?', line.strip(), re.S)
            if data:
                return float(data[0])
        if result_list:
            logging.info(f'throughput result : {sum(result_list) / len(result_list)}')
            return sum(result_list) / len(result_list)
        return 0.0

    def _get_logcat(self, lines):
        return round(self._parse_iperf_log(lines), 1)

    def get_logcat(self):
        # pytest.dut.kill_iperf()
        # 分析 iperf 测试结果
        if self.rvr_result is not None:
            return round(self.rvr_result, 1)
        return self._get_logcat(self.iperf_log_list)

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
    def get_rx_rate(self, router_info, type='TCP', corner_tool=None, db_set=''):
        router_cfg = {
            router_info.band: {
                'mode': router_info.wireless_mode,
                'security_protocol': router_info.security_protocol,
                'bandwidth': router_info.bandwidth,
            }
        }
        expect_rate = handle_expectdata(router_cfg, router_info.band, 'DL', pytest.chip_info)
        if self.skip_rx:
            corner = corner_tool.get_turntanle_current_angle() if corner_tool else ''
            rx_result_info = (
                f'{self.serialnumber} Throughput Standalone NULL Null {router_info.wireless_mode.split()[0]} '
                f'{router_info.band.split()[0]} {router_info.bandwidth.split()[0]} Rate_Adaptation '
                f'{router_info.channel} {type} DL NULL NULL {db_set} {self.rssi_num} {corner} NULL "NULL" 0 {expect_rate}')
            pytest.testResult.save_result(rx_result_info.replace(' ', ','))
            with open(pytest.testResult.detail_file, 'a', encoding='utf-8') as f:
                f.write(f'Rx {type} result : 0\n')
                f.write('-' * 40 + '\n\n')
            return 'N/A'

        rx_result_list = []
        self.rvr_result = None
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
                time.sleep(pytest.dut.iperf_wait_time)
                if pytest.connect_type == 'telnet':
                    time.sleep(15)
                rx_result = self.get_logcat()
                self.rvr_result = None
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
            logging.info(f'rx result {rx_result}')
            mcs_rx = pytest.dut.get_mcs_rx()
            logging.info(f'{rx_result}, {mcs_rx}')
            rx_result_list.append(rx_result)
            if len(rx_result_list) > self.repest_times:
                break

        if rx_result_list:
            try:
                rx_val = float(rx_result_list[0])
            except Exception:
                rx_val = 0
            if rx_val < self.throughput_threshold:
                self.skip_rx = True

        corner = corner_tool.get_turntanle_current_angle() if corner_tool else ''
        rx_result_info = (
            f'{self.serialnumber} Throughput Standalone NULL Null {router_info.wireless_mode.split()[0]} '
            f'{router_info.band.split()[0]} {router_info.bandwidth.split()[0]} Rate_Adaptation '
            f'{router_info.channel} {type} DL NULL NULL {db_set} {self.rssi_num} {corner} NULL '
            f'{mcs_rx if mcs_rx else "NULL"} {",".join(map(str, rx_result_list))} {expect_rate}')
        pytest.testResult.save_result(rx_result_info.replace(' ', ','))
        with open(pytest.testResult.detail_file, 'a', encoding='utf-8') as f:
            logging.info('writing')
            f.write(f'Rx {type} result : {rx_result}\n')
            f.write('-' * 40 + '\n\n')
        return ','.join(map(str, rx_result_list)) if rx_result_list else 'N/A'

    @step
    def get_tx_rate(self, router_info, type='TCP', corner_tool=None, db_set=''):
        router_cfg = {
            router_info.band: {
                'mode': router_info.wireless_mode,
                'security_protocol': router_info.security_protocol,
                'bandwidth': router_info.bandwidth,
            }
        }
        expect_rate = handle_expectdata(router_cfg, router_info.band, 'UL', pytest.chip_info)
        if self.skip_tx:
            corner = corner_tool.get_turntanle_current_angle() if corner_tool else ''
            tx_result_info = (
                f'{self.serialnumber} Throughput Standalone NULL Null {router_info.wireless_mode.split()[0]} '
                f'{router_info.band.split()[0]} {router_info.bandwidth.split()[0]} Rate_Adaptation '
                f'{router_info.channel} {type} UL NULL NULL {db_set} {self.rssi_num} {corner} NULL "NULL" 0 {expect_rate}')
            logging.info(tx_result_info)
            pytest.testResult.save_result(tx_result_info.replace(' ', ','))
            with open(pytest.testResult.detail_file, 'a') as f:
                f.write(f'Tx {type} result : 0\n')
                f.write('-' * 40 + '\n\n')
            return 'N/A'

        tx_result_list = []
        self.rvr_result = None

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
                time.sleep(pytest.dut.iperf_wait_time)
                if pytest.connect_type == 'telnet':
                    time.sleep(15)
                time.sleep(3)
                tx_result = self.get_logcat()
                self.rvr_result = None
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
            logging.info(f'{tx_result}, {mcs_tx}')
            tx_result_list.append(tx_result)
            if len(tx_result_list) > self.repest_times:
                break

        if tx_result_list:
            try:
                tx_val = float(tx_result_list[0])
            except Exception:
                tx_val = 0
            if tx_val < self.throughput_threshold:
                self.skip_tx = True

        corner = corner_tool.get_turntanle_current_angle() if corner_tool else ''

        tx_result_info = (
            f'{self.serialnumber} Throughput Standalone NULL Null {router_info.wireless_mode.split()[0]} '
            f'{router_info.band.split()[0]} {router_info.bandwidth.split()[0]} Rate_Adaptation '
            f'{router_info.channel} {type} UL NULL NULL {db_set} {self.rssi_num} {corner} NULL '
            f'{mcs_tx if mcs_tx else "NULL"} {",".join(map(str, tx_result_list))} {expect_rate}')
        logging.info(tx_result_info)
        pytest.testResult.save_result(tx_result_info.replace(' ', ','))
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write(f'Tx {type} result : {tx_result}\n')
            f.write('-' * 40 + '\n\n')
        return ','.join(map(str, tx_result_list)) if tx_result_list else 'N/A'

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
                time.sleep(5)
                step += 1
                info = self.checkoutput('ifconfig wlan0')
                # logging.info(f'info {info}')
                ip_address = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', info, re.S)
                if ip_address:
                    logging.info(ip_address)
                    ip_address = ip_address[0]
                if target in ip_address:
                    self.dut_ip = ip_address
                    break
                if step % 3 == 0:
                    logging.info('repeat command')
                    if cmd:
                        info = self.checkoutput(cmd)
                if step > 10:
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
        for i in range(10):
            time.sleep(1)
            rssi_info = pytest.dut.checkoutput(pytest.dut.IW_LINNK_COMMAND)
            logging.info(f'Get WiFi link status via command iw dev wlan0 link {rssi_info}')
            if 'signal' in rssi_info:
                break
        else:
            rssi_info = ''

        if 'Not connected' in rssi_info:
            with open(pytest.testResult.detail_file, 'a') as f:
                f.write('Wifi is not connected \n')
            assert False, "Wifi is not connected"
        try:
            self.rssi_num = int(re.findall(r'signal:\s+(-?\d+)\s+dBm', rssi_info, re.S)[0])
            self.freq_num = int(re.findall(r'freq:\s+(\d+)\s+', rssi_info, re.S)[0])
            with open(pytest.testResult.detail_file, 'a') as f:
                f.write(f'Rssi : {self.rssi_num}\n')
                f.write(f'Freq : {self.freq_num}\n')
        except IndexError as e:
            self.rssi_num = -1
            self.freq_num = -1
        return self.rssi_num

    step = staticmethod(step)
