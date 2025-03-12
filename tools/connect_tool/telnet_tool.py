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

        self.dut_ip = ip
        self.port = 23
        logging.info('*' * 80)
        logging.info(f'* Telnet {self.dut_ip}')
        logging.info('*' * 80)
        # self.wildcard = cmd_line_wildcard[wildcard] if type(wildcard) == str else wildcard

    def execute_cmd(self, cmd):
        self.tn.write(cmd.encode('ascii') + b'\n')
        time.sleep(1)

    def checkoutput(self, cmd, wildcard=''):
        return asyncio.run(self.telnet_client(cmd))

    @pytest.mark.asyncio
    async def telnet_client(self, command):
        async def read_all(reader, timeout=2):
            """循环读取数据，若超时无数据，则退出"""
            output = []
            while True:
                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout)
                    if not data:
                        break
                    output.append(data)
                except asyncio.TimeoutError:
                    break
            return "".join(output)

        reader, writer = '', ''
        try:
            reader, writer = await telnetlib3.open_connection(self.dut_ip, self.port)

            # 发送命令
            writer.write(command + "\n")
            await writer.drain()

            # 读取命令执行结果
            result = await read_all(reader)
            logging.info(f"Telnet Command Output: {result}")
            return result
        except Exception as e:
            logging.error(f"Telnet error: {e}")
            return None
        finally:
            if writer:
                writer.close()

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

# tl = telnet_tool('192.168.50.207','bayside')
# tl.tn.close()
# print(tl.checkoutput('iw dev wlan0 link'))
# print(tl.checkoutput('iw dev wlan0 link'))
# print('aaa')
# print(tl.checkoutput('ls'))
