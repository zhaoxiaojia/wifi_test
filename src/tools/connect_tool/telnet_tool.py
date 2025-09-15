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
import subprocess
import time

import asyncio
import telnetlib3

from src.tools.connect_tool.dut import dut

class telnet_tool(dut):
    def __init__(self, ip):
        super().__init__()
        self.dut_ip = ip
        self.port = 23
        logging.info('*' * 80)
        logging.info(f'* Telnet {self.dut_ip}')
        logging.info('*' * 80)
        self.reader = None
        self.writer = None

    def connect(self):
        if not hasattr(self, "loop"):
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        if self.reader and self.writer:
            return
        try:
            self.reader, self.writer = self.loop.run_until_complete(
                telnetlib3.open_connection(self.dut_ip, self.port)
            )
        except Exception as e:
            logging.error(f'Create telnet connection failed: {e}')

    def close(self):
        if self.writer:
            self.writer.close()
            if hasattr(self.writer, "wait_closed"):
                try:
                    self.loop.run_until_complete(self.writer.wait_closed())
                except Exception as e:
                    logging.warning(f'Error closing telnet connection: {e}')
            self.writer = None
        self.reader = None
        if hasattr(self,'loop') and not self.loop.is_closed():
            self.loop.close()

    def __del__(self):
        self.close()

    def reboot(self):
        self.checkoutput('reboot')
        time.sleep(35)
        for i in range(10):
            if self.checkoutput('ls'):
                break
            time.sleep(5)
        else:
            raise Exception('Dut lost connect')

    def login(self, username, password, prompt):
        """Login to the telnet session.

        The prompt argument is normalised to ``bytes`` to avoid ``TypeError``
        when awaiting ``readuntil``. In addition, known login strings are also
        passed as byte separators.
        """

        # Ensure prompt is bytes to match ``reader.readuntil`` expectations
        prompt = prompt.encode() if isinstance(prompt, str) else prompt
        if not (self.reader and self.writer):
            self.connect()
        if not (self.reader and self.writer):
            logging.error('Telnet login error: no connection')
            return

        async def _login():
            await self.reader.readuntil(b"login:")
            self.writer.write(username + "\n")
            await self.writer.drain()
            await self.reader.readuntil(b"Password:")
            self.writer.write(password + "\n")
            await self.writer.drain()
            await self.reader.readuntil(prompt)

        try:
            self.loop.run_until_complete(_login())
        except TypeError as e:
            logging.error(f'Telnet login failed (TypeError): {e}')
        except Exception as e:
            logging.error(f'Telnet login failed: {e}')

    async def _read_all(self, timeout=2):
        output = []
        while True:
            try:
                data = await asyncio.wait_for(self.reader.read(1024), timeout)
                if not data:
                    break
                output.append(data)
            except asyncio.TimeoutError:
                break
        return "".join(output)

    def execute_cmd(self, cmd):
        if not (self.reader and self.writer):
            self.connect()
        if self.writer:
            self.writer.write(cmd + "\n")
            self.loop.run_until_complete(self.writer.drain())
            time.sleep(1)
        else:
            logging.error('Telnet execute cmd error: no connection')

    def checkoutput(self, cmd, wildcard=''):
        if not (self.reader and self.writer):
            self.connect()
        if not (self.reader and self.writer):
            return None
        self.writer.write(cmd + "\n")
        self.loop.run_until_complete(self.writer.drain())
        return self.loop.run_until_complete(self._read_all())

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

# tl = telnet_tool('192.168.50.207')
# tl.close()
# print(tl.checkoutput('iw dev wlan0 link'))
# print(tl.checkoutput('iw dev wlan0 link'))
# print('aaa')
# print(tl.checkoutput('ls'))
