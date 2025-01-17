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
import time

import psutil
import pytest

from tools.ixchariot import ix


class dut():
    count = 0
    DMESG_COMMAND = 'dmesg -S'
    CLEAR_DMESG_COMMAND = 'dmesg -c'

    SETTING_ACTIVITY_TUPLE = 'com.android.tv.settings', '.MainSettings'
    MORE_SETTING_ACTIVITY_TUPLE = 'com.droidlogic.tv.settings', '.more.MorePrefFragmentActivity'

    SKIP_OOBE = "pm disable com.google.android.tungsten.setupwraith;settings put secure user_setup_complete 1;settings put global device_provisioned 1;settings put secure tv_user_setup_complete 1"
    # iperf 相关命令
    IPERF_TEST_TIME = 30
    IPERF_WAIT_TIME = IPERF_TEST_TIME + 5

    def iperf(args, command='iperf'):
        return f'{command} {args}'

    IPERF_SERVER = {'TCP': iperf(' -s -w 4m -i 1'),
                    'UDP': iperf(' -s -u -i 1 ')}

    IPERF_CLIENT_REGU = {'TCP': {'tx': iperf(' -c {} -w 4m -i 1 -t {} -P{}'),
                                 'rx': iperf(' -c {} -w 4m -i 1 -t {} -P{}')},
                         'UDP': {'tx': iperf(' -c {} -u -i1 -b 800M -t {} -P{}'),
                                 'rx': iperf(' -c {} -u -i1 -b 300M -t {} -P{}')}}

    IPERF_MULTI_SERVER = 'iperf -s -w 4m -i 1 {}&'
    IPERF_MULTI_CLIENT_REGU = '.iperf -c {} -w 4m -i 1 -t 60 -p {}'

    IPERF3_CLIENT_UDP_REGU = 'iperf3 -c {} -i 1 -t 60 -u -b 120M -l63k -P {}'

    IPERF_KILL = 'killall -9 iperf'
    IPERF_WIN_KILL = 'taskkill /im iperf.exe -f'
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
        self.rvr_tool = pytest.config_yaml.get_note('rvr')['tool']
        self.pair = pytest.config_yaml.get_note('rvr')['pair']
        self.repest_times = pytest.config_yaml.get_note('rvr')['repeat']
        self._dut_ip = ''
        self._pc_ip = ''
        if self.rvr_tool == 'iperf':
            self.test_tool = pytest.config_yaml.get_note('rvr')[self.rvr_tool]['version']
            self.tool_path = pytest.config_yaml.get_note('rvr')[self.rvr_tool]['path'] or ''
            logging.info(f'test_tool {self.test_tool}')

        if self.rvr_tool == 'ixchariot':
            self.ix = ix()
            self.test_tool = pytest.config_yaml.get_note('rvr')[self.rvr_tool]
            self.script_path = self.test_tool['path']
            logging.info(f'path {self.script_path}')
            logging.info(f'test_tool {self.test_tool}')
            self.ix.modify_tcl_script("set ixchariot_installation_dir ",
                                      f"set ixchariot_installation_dir \"{self.script_path}\"\n")

    @property
    def dut_ip(self):
        if self._dut_ip == '': self._dut_ip = self.get_dut_ip()
        return self._dut_ip

    @property
    def pc_ip(self):
        if self._pc_ip == '': self._pc_ip = self.get_pc_ip()
        return self._pc_ip

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
        if not isinstance(command, list):
            command = command.split()
        try:
            info = subprocess.check_output(command, encoding='gbk' if pytest.win_flag else 'utf-8')
        except Exception:
            info = ''
        return info

    def kill_iperf(self):
        try:
            pytest.dut.subprocess_run(pytest.dut.IPERF_KILL)
        except Exception:
            ...
        try:
            pytest.dut.subprocess_run(pytest.dut.IPERF_KILL.replace('iperf', 'iperf3'))
        except Exception:
            ...

        try:
            pytest.dut.popen_term(pytest.dut.IPERF_WIN_KILL)
        except Exception:
            ...
        try:
            pytest.dut.popen_term(pytest.dut.IPERF_WIN_KILL.replace('iperf', 'iperf3'))
        except Exception:
            ...

    def run_iperf(self, command, adb, direction='tx', iperf3=False):
        def run_server():
            if adb and pytest.connect_type == 'telnet':
                pytest.dut.checkoutput(command)
            else:
                with open(f'rvr_log_{pytest.dut.serialnumber}.txt', 'w') as f:
                    popen = subprocess.Popen(command.split(), stdout=f, encoding='utf-8')
                return popen
            # logging.info(subprocess.run('tasklist | findstr "iperf"'.replace('iperf',pc_ipef),shell=True,encoding='gbk'))
            # logging.info(pytest.dut.checkoutput('ps -A|grep "iperf"'.replace('iperf',dut_iperf)))

        if os.path.exists(f'rvr_log_{pytest.dut.serialnumber}.txt') and '-s' in command:
            # for proc in psutil.process_iter():
            #     try:
            #         files = proc.open_files()
            #         for f in files:
            #             if f.path == f'rvr_log_{pytest.dut.serialnumber}.txt':
            #                 proc.kill()  # Kill the process that occupies the file
            #     except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            #         pass
            os.remove(f'rvr_log_{pytest.dut.serialnumber}.txt')

        if adb:
            if iperf3:
                command = 'iperf3 -s -1'
            if pytest.connect_type == 'adb':
                command = f'adb -s {adb} shell ' + command
        else:
            if iperf3:
                command = f'iperf3 -c {pytest.dut.dut_ip} -i1 -t30 -P5'
                if direction == 'tx':
                    command = f'iperf3 -c {pytest.dut.dut_ip} -i1 -t30 -P5 -R'

        logging.info(f'{adb} run command {command} ')

        if re.findall(r'iperf[3]?.*?-s', command):
            popen = run_server()
        else:
            if adb and pytest.connect_type == 'telnet':
                pytest.dut.checkoutput(command)
            popen = subprocess.Popen(command.split(), encoding='utf-8')
        return popen

    def get_logcat(self, pair, adb):
        # pytest.dut.kill_iperf()
        # 分析 iperf 测试结果
        result_list = []
        if os.path.exists(f'rvr_log_{pytest.dut.serialnumber}.txt'):
            with open(f'rvr_log_{pytest.dut.serialnumber}.txt', 'r') as f:
                for line in f.readlines():
                    # if line.strip(): logging.info(f'line : {line.strip()}')
                    if pair != 1:
                        if '[SUM]' not in line:
                            continue
                    if re.findall(r'.*?\d+\.\d*-\s*\d+\.\d*.*?(\d+\.*\d*)\s+Mbits/sec.*?', line.strip(), re.S):
                        result_list.append(
                            float(
                                re.findall(r'.*?\d+\.\d*-\s*\d+\.\d*.*?(\d+\.*\d*)\s+Mbits/sec.*?', line.strip(), re.S)[
                                    0]))

        if result_list:
            logging.info(f'{sum(result_list) / len(result_list)}')
            logging.info(f'{result_list}')
            result = sum(result_list) / len(result_list)
        else:
            result = 0
        return round(result, 1)

    def get_pc_ip(self):
        if pytest.win_flag:
            ipfoncig_info = pytest.dut.checkoutput_term('ipconfig').strip()
            pc_ip = re.findall(r'IPv4 地址.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
        else:
            ipfoncig_info = pytest.dut.checkoutput_term('ifconfig')
            pc_ip = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
        if not pc_ip: assert False, "Can't get pc ip"
        return pc_ip

    def get_dut_ip(self):
        if pytest.connect_type == 'telnet':
            return pytest.dut.ip
        dut_info = pytest.dut.checkoutput('ifconfig wlan0')
        dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)
        if dut_ip:
            dut_ip = dut_ip[0]
        if not dut_ip: assert False, "Can't get dut ip"
        return dut_ip

    @step
    def get_rx_rate(self, router_info, rssi_num, type='TCP', corner_tool=None, db_set=''):
        rx_result_list = []
        for _ in range(5):
            logging.info('run rx')
            rx_result = 0
            mcs_rx = 0
            # clear mcs data
            # pytest.dut.checkoutput(pytest.dut.CLEAR_DMESG_COMMAND)
            # pytest.dut.checkoutput(pytest.dut.MCS_RX_CLEAR_COMMAND)
            # kill iperf
            if self.rvr_tool == 'iperf':
                pytest.dut.kill_iperf()
                time.sleep(1)
                adb_popen = pytest.dut.run_iperf(self.tool_path + pytest.dut.IPERF_SERVER[type], self.serialnumber)
                time.sleep(2)
                pc_popen = pytest.dut.run_iperf(
                    pytest.dut.IPERF_CLIENT_REGU[type]['rx'].format(
                        self.dut_ip, pytest.dut.IPERF_TEST_TIME,
                        self.pair), '', direction='rx')
                time.sleep(pytest.dut.IPERF_WAIT_TIME)
                if pytest.connect_type == 'telnet':
                    time.sleep(15)
                rx_result = self.get_logcat(self.pair, self.serialnumber)

            if self.rvr_tool == 'ixchariot':
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
            # get mcs data
            mcs_rx = pytest.dut.get_mcs_rx()
            logging.info(f'expected rate {router_info.expected_rate.split()[1]}')
            logging.info(f'{rx_result}, {mcs_rx}')
            rx_result_list.append(rx_result)
            if len(rx_result_list) > self.repest_times:
                break
        corner = corner_tool.get_turntanle_current_angle() if corner_tool else ''

        rx_result_info = (
            f'{self.serialnumber} Throughput Standalone NULL Null {router_info.wireless_mode.split()[0]} '
            f'{router_info.band.split()[0]} {router_info.bandwidth.split()[0]} Rate_Adaptation '
            f'{router_info.channel} {type} DL NULL NULL {db_set} {rssi_num} {corner} NULL '
            f'{mcs_rx if mcs_rx else "NULL"} {",".join(map(str, rx_result_list))}')
        pytest.testResult.save_result(rx_result_info.replace(' ', ','))
        with open(pytest.testResult.detail_file, 'a', encoding='utf-8') as f:
            logging.info('writing')
            f.write(f'Rx {type} result : {rx_result}\n')
            f.write('-' * 40 + '\n\n')
        return rx_result_list

    @step
    def get_tx_rate(self, router_info, rssi_num, type='TCP', corner_tool=None,
                    db_set=''):
        global tx_result
        tx_result_list = []
        for _ in range(5):
            logging.info('run tx ')
            tx_result = 0
            mcs_tx = 0
            # pytest.dut.checkoutput(pytest.dut.CLEAR_DMESG_COMMAND)
            # pytest.dut.checkoutput(pytest.dut.MCS_TX_KEEP_GET_COMMAND)
            # kill iperf
            if self.rvr_tool == 'iperf':
                pytest.dut.kill_iperf()
                time.sleep(1)
                if self.test_tool == 'iperf3':
                    adb_popen = pytest.dut.run_iperf(self.tool_path + pytest.dut.IPERF_CLIENT_REGU[type]['tx'].format(
                        self.pc_ip,
                        pytest.dut.IPERF_TEST_TIME,
                        self.pair), self.serialnumber)
                    pc_popen = pytest.dut.run_iperf(pytest.dut.IPERF_SERVER[type], '')
                else:
                    pc_popen = pytest.dut.run_iperf(pytest.dut.IPERF_SERVER[type], '')
                    time.sleep(2)
                    adb_popen = pytest.dut.run_iperf(self.tool_path + pytest.dut.IPERF_CLIENT_REGU[type]['tx'].format(
                        self.pc_ip,
                        pytest.dut.IPERF_TEST_TIME,
                        self.pair), self.serialnumber)

                time.sleep(pytest.dut.IPERF_WAIT_TIME)
                if pytest.connect_type == 'telnet':
                    time.sleep(15)
                time.sleep(3)
                tx_result = self.get_logcat(self.pair if type == 'TCP' else 1, self.serialnumber)

            if self.rvr_tool == 'ixchariot':
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
            logging.info(f'expected rate {router_info.expected_rate.split()[0]}')
            logging.info(f'{tx_result}, {mcs_tx}')
            tx_result_list.append(tx_result)
            if len(tx_result_list) > self.repest_times:
                break
        # corner = corner_tool.get_turntanle_current_angle() if corner_needed else corner_set
        corner = ''
        tx_result_info = (
            f'{self.serialnumber} Throughput Standalone NULL Null {router_info.wireless_mode.split()[0]} '
            f'{router_info.band.split()[0]} {router_info.bandwidth.split()[0]} Rate_Adaptation '
            f'{router_info.channel} {type} UL NULL NULL {db_set} {rssi_num} {corner} NULL '
            f'{mcs_tx if mcs_tx else "NULL"} {",".join(map(str, tx_result_list))}')
        logging.info(tx_result_info)
        pytest.testResult.save_result(tx_result_info.replace(' ', ','))
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write(f'Tx {type} result : {tx_result}\n')
            f.write('-' * 40 + '\n\n')
        return tx_result_list

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
            rssi_num = int(re.findall(r'signal:\s+(-?\d+)\s+dBm', rssi_info, re.S)[0])
            # freq_num = int(re.findall(r'freq:\s+(\d+)\s+', rssi_info, re.S)[0])
            with open(pytest.testResult.detail_file, 'a') as f:
                f.write(f'Rssi : {rssi_num}\n')
                # f.write(f'Freq : {freq_num}\n')
        except IndexError as e:
            rssi_num = -1
            # freq_num = -1
        return rssi_num

    step = staticmethod(step)
