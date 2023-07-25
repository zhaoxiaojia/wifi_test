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
import subprocess
import time
import pytest
import re
import signal


class Iperf:
    def run_iperf(self, type='rx'):
        pytest.executer.root()
        pytest.executer.remount()
        if pytest.executer.checkoutput('[ -e /system/bin/iperf ] && echo yes || echo no').strip() != 'yes':
            logging.info('no iperf')
            pytest.executer.push('res\\iperf', '/system/bin/')
        pytest.executer.checkoutput('chmod a+x /system/bin/iperf')
        pytest.executer.subprocess_run(pytest.executer.IPERF_KILL)
        # try:
        pytest.executer.popen_term(pytest.executer.IPERF_WIN_KILL)
        # except Exception as e:
        #     ...
        dut_ip = pytest.executer.checkoutput('ifconfig wlan0 |egrep -o "inet addr:[^ ]*"|cut -d : -f 2').strip()
        ipfoncig_info = pytest.executer.checkoutput_term('ipconfig').strip()
        pc_ip = re.findall(r'IPv4 地址.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
        logging.info(f'dut_ip {dut_ip}')
        logging.info(f'adb -s {pytest.executer.serialnumber} shell ' + pytest.executer.IPERF_SERVER)
        if type == 'rx':
            server = subprocess.Popen(
                (f'adb -s {pytest.executer.serialnumber} shell ' + pytest.executer.IPERF_SERVER).split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, encoding='utf-8')
            logging.info(pytest.executer.IPERF_CLIENT_REGU.format(dut_ip, pytest.executer.IPERF_TEST_TIME, 4))
            time.sleep(1)
            client = subprocess.Popen(
                pytest.executer.IPERF_CLIENT_REGU.format(dut_ip, pytest.executer.IPERF_TEST_TIME, 4).split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, encoding='utf-8')
        else:
            server = subprocess.Popen(pytest.executer.IPERF_SERVER.split(), stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, encoding='utf-8')
            time.sleep(1)
            client = subprocess.Popen(
                (f'adb -s {pytest.executer.serialnumber} shell ' +
                 pytest.executer.IPERF_CLIENT_REGU.format(pc_ip,
                                                          pytest.executer.IPERF_TEST_TIME,
                                                          4)).split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, encoding='utf-8')
            logging.info(pytest.executer.IPERF_CLIENT_REGU.format(dut_ip, pytest.executer.IPERF_TEST_TIME, 4))
        start = time.time()
        while True and time.time() - start < pytest.executer.IPERF_WAIT_TIME:
            line = client.stdout.readline()
            if not line:
                # logging.info(f'get_readline {log}')
                continue
            if line is None:
                break
            logging.info(line.strip())
            if re.findall(r'\[SUM\]\s+0\.0-[3|4|5|6|7]\d\.\d+.*?\d+\s+Mbits/sec', line,
                          re.S):  # and 'receiver' in line:
                if not isinstance(server, subprocess.Popen):
                    logging.warning('pls pass in the popen object')
                    return 'pls pass in the popen object'
                os.kill(server.pid, signal.SIGTERM)
                server.terminate()
                return True
        return False
