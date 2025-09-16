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
        self.command_post_delay = 0.2

    def _ensure_loop(self):
        loop = getattr(self, "loop", None)
        if loop is None or loop.is_closed():
            loop = asyncio.new_event_loop()
            self.loop = loop
        asyncio.set_event_loop(loop)
        return loop

    def _connection_active(self) -> bool:
        if not (self.reader and self.writer):
            return False

        reader_at_eof = getattr(self.reader, "at_eof", None)
        if callable(reader_at_eof):
            try:
                if reader_at_eof():
                    return False
            except Exception:
                pass

        reader_exception = getattr(self.reader, "exception", None)
        if callable(reader_exception):
            try:
                if reader_exception():
                    return False
            except Exception:
                pass

        writer_is_closing = getattr(self.writer, "is_closing", None)
        if callable(writer_is_closing):
            try:
                if writer_is_closing():
                    return False
            except Exception:
                pass

        writer_closed = getattr(self.writer, "closed", None)
        if isinstance(writer_closed, bool) and writer_closed:
            return False

        transport = getattr(self.writer, "transport", None)
        if transport is not None:
            transport_is_closing = getattr(transport, "is_closing", None)
            if callable(transport_is_closing):
                try:
                    if transport_is_closing():
                        return False
                except Exception:
                    pass

        return True

    def _reset_connection_state(self):
        loop = getattr(self, "loop", None)
        if self.writer:
            try:
                self.writer.close()
                if (
                    loop
                    and not loop.is_closed()
                    and hasattr(self.writer, "wait_closed")
                ):
                    loop.run_until_complete(self.writer.wait_closed())
            except Exception as e:
                logging.warning(f'Error shutting down telnet writer: {e}')
        self.writer = None
        self.reader = None

    def connect(self):
        loop = self._ensure_loop()
        if self._connection_active():
            return
        self._reset_connection_state()
        loop = self._ensure_loop()
        try:
            self.reader, self.writer = loop.run_until_complete(
                telnetlib3.open_connection(self.dut_ip, self.port)
            )
        except Exception as e:
            logging.error(f'Create telnet connection failed: {e}')

    def close(self):
        self._reset_connection_state()
        loop = getattr(self, "loop", None)
        if loop:
            try:
                if not loop.is_closed():
                    loop.close()
            except Exception as e:
                logging.warning(f'Error closing telnet loop: {e}')
            finally:
                self.loop = None

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

    async def _read_all(self, timeout=5):
        output = []
        while True:
            try:
                data = await asyncio.wait_for(self.reader.read(1024), timeout)
                if not data:
                    break
                output.append(data)
            except asyncio.TimeoutError:
                break
        result = "".join(output)
        if not result and not self._connection_active():
            raise ConnectionError('Telnet connection lost')
        return result

    async def _send_command_and_collect(self, cmd: str, delay: float = 0.0):
        """写入命令后等待设备回显并收集所有输出。"""

        try:
            self.writer.write(cmd + "\n")
            await self.writer.drain()
        except Exception as e:
            raise ConnectionError(f'Failed to send telnet command: {e}') from e
        if delay:
            await asyncio.sleep(delay)
        return await self._read_all()

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
        self.connect()
        if not self._connection_active():
            logging.error('Telnet checkoutput error: no connection')
            return ''
        try:
            output = self.loop.run_until_complete(
                self._send_command_and_collect(cmd, self.command_post_delay)
            )
        except ConnectionError as e:
            logging.warning(f'Telnet command failed, reconnecting: {e}')
            self._reset_connection_state()
            self.connect()
            if not self._connection_active():
                return ''
            output = self.loop.run_until_complete(
                self._send_command_and_collect(cmd, self.command_post_delay)
            )
        if not output and not self._connection_active():
            self._reset_connection_state()
            self.connect()
            if not self._connection_active():
                return ''
            output = self.loop.run_until_complete(
                self._send_command_and_collect(cmd, self.command_post_delay)
            )
        return output

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
