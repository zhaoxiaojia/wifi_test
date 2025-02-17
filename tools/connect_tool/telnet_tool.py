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
import os.path
import re
import subprocess
import telnetlib
import time
from threading import Thread

import pytest
import asyncio
import telnetlib3

from tools.connect_tool.dut import dut

cmd_line_wildcard = {
    'sandia': b'sandia:/ #',
    'sandia_latam': b'sandia_isdb:/ #',
    'sandia_hkc': b'sandia manu:/ #',
    'sandia_dvb': b'sandia_dvb:/ #',
    'bayside': b'bayside:/ #'
}


class telnet_tool(dut):
    def __init__(self, ip, wildcard):
        super().__init__()

        self.ip = ip
        self.port = 23
        # self.wildcard = cmd_line_wildcard[wildcard] if type(wildcard) == str else wildcard
        # try:
        #     logging.info(f'Try to connect {ip} {wildcard}')
        #     self.tn = telnetlib.Telnet()
        #     self.tn.open(self.ip, port=23)
        #     self.tn.read_until(self.wildcard).decode('utf-8')
        #     logging.info('*' * 80)
        #     logging.info(f'* Telnet {self.ip}')
        #     logging.info('*' * 80)
        # except Exception as f:
        #     logging.info(f)

    def execute_cmd(self, cmd):
        self.tn.write(cmd.encode('ascii') + b'\n')
        time.sleep(1)

    def checkoutput(self, cmd, wildcard=''):

        # if not wildcard:
        #     wildcard = self.wildcard
        # try:
        #     self.tn.write('\n'.encode('ascii') + b'\n')
        #     res = self.tn.read_until(wildcard).decode('gbk')
        # except Exception as e:
        #     self.tn.open(self.ip)
        #     self.tn.write('\n'.encode('ascii') + b'\n')
        #     res = self.tn.read_until(wildcard).decode('gbk')
        # if re.findall(r'iperf[3]?.*?-s', cmd):
        #     cmd += '&'
        # logging.info(f'telnet {self.ip} :{cmd}')
        #
        # self.tn.write(cmd.encode('ascii') + b'\n')
        # res = self.tn.read_until(wildcard).decode('gbk')
        # # res = self.tn.read_very_eager().decode('gbk')
        # time.sleep(1)
        # return res.strip()
        return asyncio.run(self.telnet_client(cmd))

    async def telnet_client(self, command):
        reader, writer = await telnetlib3.open_connection(self.ip, self.port)

        async def safe_read():
            try:
                return await asyncio.wait_for(reader.read(1024), timeout=2)  # 2 秒超时
            except asyncio.TimeoutError:
                return "Read timeout"

        async def read_all(timeout=2):
            """循环读取数据，若超时无数据，则退出"""
            while True:
                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout)
                    if not data:  # 服务器关闭连接
                        break
                    print(data, end="")
                except asyncio.TimeoutError:
                    break

        # 发送命令
        writer.write(command + "\n")
        await writer.drain()

        # 读取命令执行结果
        result = await read_all()
        logging.info(f"Telnet Command Output: {result}")
        # 关闭连接
        writer.close()
        return result

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

# tl = TelnetInterface('192.168.31.95','bayside')
# tl.tn.close()
# print(tl.checkoutput('iw dev wlan0 link'))
# print(tl.checkoutput('iw dev wlan0 link'))
# print('aaa')
# print(tl.checkoutput('ls'))
