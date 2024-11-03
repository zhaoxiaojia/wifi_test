#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : Iperf.py
# Time       ：2023/7/24 10:26
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import os
import re
import signal
import subprocess
import time

import pytest


class Iperf:
    def run_iperf(self, type='rx'):
        pytest.dut.root()
        pytest.dut.remount()
        if pytest.dut.checkoutput('[ -e /system/bin/iperf ] && echo yes || echo no').strip() != 'yes':
            logging.info('no iperf')
            pytest.dut.push('res\\iperf', '/system/bin/')
        pytest.dut.checkoutput('chmod a+x /system/bin/iperf')
        pytest.dut.subprocess_run(pytest.dut.IPERF_KILL)
        # try:
        pytest.dut.popen_term(pytest.dut.IPERF_WIN_KILL)
        # except Exception as e:
        #     ...
        dut_ip = pytest.dut.checkoutput('ifconfig wlan0 |egrep -o "inet addr:[^ ]*"|cut -d : -f 2').strip()
        ipfoncig_info = pytest.dut.checkoutput_term('ipconfig').strip()
        pc_ip = re.findall(r'IPv4 地址.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
        logging.info(f'dut_ip {dut_ip}')
        if type == 'rx':
            logging.info('iperf rx running')
            logging.info(
                f'adb -s {pytest.dut.serialnumber} shell ' + pytest.dut.IPERF_SERVER['TCP'])
            with open('temp.txt', 'w') as f:
                server = subprocess.Popen((f'adb -s {pytest.dut.serialnumber} shell ' +
                                           pytest.dut.IPERF_SERVER['TCP']).split(), stdout=f,encoding='utf-8')
            time.sleep(1)
            logging.info(
                pytest.dut.IPERF_CLIENT_REGU['TCP']['rx'].format(dut_ip, pytest.dut.IPERF_TEST_TIME, 4))
            subprocess.Popen(
                pytest.dut.IPERF_CLIENT_REGU['TCP']['rx'].format(dut_ip, pytest.dut.IPERF_TEST_TIME,
                                                                      4).split())

        else:
            logging.info('iperf tx running')
            logging.info(
                pytest.dut.IPERF_SERVER['TCP'])
            with open('temp.txt', 'w') as f:
                server = subprocess.Popen(pytest.dut.IPERF_SERVER['TCP'].split(), stdout=f, encoding='utf-8')
            time.sleep(1)
            logging.info(f'adb -s {pytest.dut.serialnumber} shell ' +
                         pytest.dut.IPERF_CLIENT_REGU['TCP']['tx'].format(dut_ip, pytest.dut.IPERF_TEST_TIME,
                                                                               4))
            subprocess.Popen(
                (f'adb -s {pytest.dut.serialnumber} shell ' +
                 pytest.dut.IPERF_CLIENT_REGU['TCP']['tx'].format(pc_ip,
                                                                       pytest.dut.IPERF_TEST_TIME,
                                                                       4)), shell=True)

        time.sleep(pytest.dut.IPERF_WAIT_TIME)
        logging.info(pytest.dut.IPERF_TEST_TIME)
        logging.info(pytest.dut.IPERF_WAIT_TIME)
        if not isinstance(server, subprocess.Popen):
            logging.warning('pls pass in the popen object')
            return 'pls pass in the popen object'
        os.kill(server.pid, signal.SIGTERM)
        server.terminate()
        with open('temp.txt', 'r') as f:
            for line in f.readlines():
                logging.info(line.strip())
                if re.findall(rf'\[SUM\]\s+0\.0-{pytest.dut.IPERF_TEST_TIME}\.\d+.*?\d+\s+Mbits/sec', line.strip(),
                              re.S):  # and 'receiver' in line:
                    logging.info('*' * 50)
                    logging.info(line)
                    return True
        return False
