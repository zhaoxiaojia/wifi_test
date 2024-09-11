#!/usr/bin/env python 
# -*- coding: utf-8 -*- 


"""
# File       : telnet_tool.py
# Time       ：2023/6/30 16:57
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import re
import subprocess
import telnetlib
import time
from threading import Thread

import pytest

from tools.connect_tool.dut import Dut

cmd_line_wildcard = {
    'sandia': b'sandia:/ #',
    'sandia_latam': b'sandia_isdb:/ #',
    'sandia_hkc': b'sandia manu:/ #',
    'sandia_dvb': b'sandia_dvb:/ #',
    'bayside': b'bayside:/ #'
}

class TelnetInterface(Dut):
    def __init__(self, ip, wildcard):
        super().__init__()
        self.ip = ip
        self.wildcard = cmd_line_wildcard[wildcard] if type(wildcard) == str else wildcard
        try:
            logging.info(f'Try to connect {ip}')
            self.tn = telnetlib.Telnet()
            self.tn.open(self.ip, port=23)
            self.tn.read_until(self.wildcard).decode('utf-8')
            logging.info('telnet init done')
            # print('telnet init done')
        except Exception as f:
            logging.info(f)
            return None

    def execute_cmd(self, cmd):
        self.tn.write(cmd.encode('ascii') + b'\n')
        time.sleep(1)

    def checkoutput(self, cmd, wildcard=''):

        def run_iperf():
            self.tn.write(cmd.encode('ascii') + b'\n')
            res = self.tn.read_until(b'[SUM]  0.0-3').decode('gbk')
            with open('temp.txt', 'w') as f:
                f.write(res)

        if not wildcard:
            wildcard = self.wildcard
        try:
            self.tn.write('ls'.encode('ascii') + b'\n')
            res = self.tn.read_until(wildcard).decode('gbk')
        except AttributeError as e:
            self.tn.open(self.ip)
            # res = self.tn.read_until(wildcard).decode('gbk')
        if re.findall(r'iperf[3]?.*?-s', cmd):
            cmd += '&'
        logging.info(f'telnet command {cmd}')

        if re.findall(r'iperf[3]?.*?-s', cmd):
            logging.info('run thread')
            t = Thread(target=run_iperf)
            t.daemon = True
            t.start()
        else:
            self.tn.write(cmd.encode('ascii') + b'\n')
            res = self.tn.read_until(wildcard).decode('gbk')
        # res = self.tn.read_very_eager().decode('gbk')
        time.sleep(1)
        return res.strip()

    def popen_term(self, command):
        return subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def subprocess_run(self, cmd):
        return self.checkoutput(cmd)

    def root(self):
        ...

    def remount(self):
        ...

    def getprop(self, key):
        return self.checkoutput('getprop %s' % key)

    def get_mcs_tx(self):
        return 'mcs_tx'

    def get_mcs_rx(self):
        return 'mcs_rx'

# tl = TelnetInterface('192.168.50.254')
# tl.tn.close()
# print(tl.checkoutput('iw wlan0 link'))
# print('aaa')
# print(tl.checkoutput('ls'))
