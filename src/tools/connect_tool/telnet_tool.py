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
import threading
import telnetlib3

from src.tools.connect_tool.dut import dut


class telnet_tool(dut):
    def __init__(self, ip):
        super().__init__()
        self.ip = ip
        self.port = 23
        logging.info('*' * 80)
        logging.info(f'* Telnet {self.ip}')
        logging.info('*' * 80)
        self.reader = None
        self.writer = None
        self.loop = None
        self._loop_thread = None
        self._loop_ready = threading.Event()

    def _ensure_loop(self):
        if self.loop and self.loop.is_closed():
            self.loop = None

        if not self.loop:
            self.loop = asyncio.new_event_loop()

        if self._loop_thread and not self._loop_thread.is_alive():
            self._loop_thread = None

        if not self._loop_thread:
            self._loop_ready.clear()

            def _run_loop():
                try:
                    asyncio.set_event_loop(self.loop)
                    self._loop_ready.set()
                    self.loop.run_forever()
                except Exception as exc:
                    logging.debug(f'Telnet loop error: {exc}')
                finally:
                    self._loop_ready.set()

            self._loop_thread = threading.Thread(
                target=_run_loop,
                name='telnet-tool-loop',
                daemon=True,
            )
            self._loop_thread.start()
            self._loop_ready.wait()

    def _connection_alive(self):
        if not (self.reader and self.writer):
            return False
        try:
            if hasattr(self.reader, "at_eof") and self.reader.at_eof():
                return False
        except Exception as exc:
            logging.debug(f"reader.at_eof check failed: {exc}")
            return False
        try:
            if hasattr(self.writer, "is_closing") and self.writer.is_closing():
                return False
        except Exception as exc:
            logging.debug(f"writer.is_closing check failed: {exc}")
            return False
        return True

    def _reset_connection_state(self):
        # Ensure the caller sees a disconnected state before attempting reconnect.
        writer = self.writer
        self.reader = None
        self.writer = None
        if writer:
            try:
                if self.loop and self.loop.is_running():
                    self.loop.call_soon_threadsafe(writer.close)
                else:
                    writer.close()
            except Exception as exc:
                logging.debug(f"Error closing telnet writer: {exc}")

    def connect(self):
        self._ensure_loop()
        if self._connection_alive():
            return
        try:
            future = asyncio.run_coroutine_threadsafe(
                telnetlib3.open_connection(self.ip, self.port),
                self.loop,
            )
            self.reader, self.writer = future.result()
        except Exception as exc:
            logging.error(f"Telnet connect failed: {exc}")
            self.reader = None
            self.writer = None

    def close(self):
        try:
            self._stop_telnet_iperf_thread()
        except AttributeError:
            # Base class may not be initialised yet in exceptional cases.
            pass

        writer = self.writer
        self.reader = None
        self.writer = None

        if writer:
            try:
                if self.loop and self.loop.is_running():
                    self.loop.call_soon_threadsafe(writer.close)
                else:
                    writer.close()
            except Exception as exc:
                logging.debug(f'Error closing telnet writer: {exc}')

            if hasattr(writer, "wait_closed") and self.loop:
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        writer.wait_closed(), self.loop
                    )
                    future.result(timeout=3)
                except Exception as e:
                    logging.warning(f'Error closing telnet connection: {e}')

        if self.loop:
            try:
                if self.loop.is_running():
                    self.loop.call_soon_threadsafe(self.loop.stop)
                    if self._loop_thread:
                        self._loop_thread.join(timeout=2)
                if not self.loop.is_closed():
                    self.loop.close()
            except Exception as exc:
                logging.debug(f'Error stopping telnet loop: {exc}')

        self.loop = None
        self._loop_thread = None
        if self._loop_ready:
            self._loop_ready.clear()

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
            future = asyncio.run_coroutine_threadsafe(_login(), self.loop)
            future.result()
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

    async def _execute_command(self, cmd):
        self.writer.write(cmd + "\n")
        await self.writer.drain()
        return await self._read_all()

    def checkoutput(self, cmd, wildcard=''):
        logging.info(f'ip {self.ip} {id(self)}')
        self._ensure_loop()

        for attempt in range(2):
            if not self._connection_alive():
                self._reset_connection_state()
                self.connect()
            if not self._connection_alive():
                return None
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._execute_command(cmd),
                    self.loop,
                )
                return future.result()
            except (ConnectionResetError, RuntimeError) as exc:
                logging.warning(
                    f"Telnet command '{cmd}' failed on attempt {attempt + 1}: {exc}"
                )
                self._reset_connection_state()
                self.connect()
            except Exception as exc:
                logging.warning(
                    f"Telnet command '{cmd}' failed on attempt {attempt + 1}: {exc}"
                )
                self._reset_connection_state()
                self.connect()
        logging.error(f"Telnet command '{cmd}' failed after retries")
        return None

    def start_throughput_stream(self, cmd, stop_event, line_callback=None, read_timeout=0.5):
        self._ensure_loop()

        if not self._connection_alive():
            self._reset_connection_state()
            self.connect()

        if not self._connection_alive():
            logging.error('Telnet throughput stream failed: no active connection')
            return None

        async def _stream():
            buffer = ''
            try:
                self.writer.write(cmd + "\n")
                await self.writer.drain()
            except Exception as exc:
                logging.error(f'Failed to send throughput command: {exc}')
                return

            async def _drain_pending(timeout):
                nonlocal buffer
                while True:
                    try:
                        chunk = await asyncio.wait_for(
                            self.reader.readline(), timeout=timeout
                        )
                    except asyncio.TimeoutError:
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logging.debug(f'Throughput stream read error: {exc}')
                        break
                    if not chunk:
                        break
                    buffer += chunk
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        clean_line = line.rstrip('\r')
                        if clean_line and line_callback:
                            try:
                                line_callback(clean_line)
                            except Exception as cb_exc:
                                logging.debug(f'Throughput callback error: {cb_exc}')

            try:
                while not stop_event.is_set():
                    try:
                        chunk = await asyncio.wait_for(
                            self.reader.readline(), timeout=read_timeout
                        )
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logging.debug(f'Throughput stream read error: {exc}')
                        break

                    if not chunk:
                        break
                    buffer += chunk
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        clean_line = line.rstrip('\r')
                        if clean_line and line_callback:
                            try:
                                line_callback(clean_line)
                            except Exception as cb_exc:
                                logging.debug(f'Throughput callback error: {cb_exc}')

                await _drain_pending(0.2)

                if buffer.strip() and line_callback:
                    try:
                        line_callback(buffer.strip())
                    except Exception as cb_exc:
                        logging.debug(f'Throughput callback error: {cb_exc}')

                try:
                    self.writer.write("\n")
                    await self.writer.drain()
                    await asyncio.wait_for(self.reader.readline(), timeout=1)
                except asyncio.TimeoutError:
                    logging.debug('Timeout while restoring telnet prompt after throughput stream')
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logging.debug(f'Error restoring telnet prompt: {exc}')
            except asyncio.CancelledError:
                logging.debug('Throughput stream cancelled')
                raise

        try:
            return asyncio.run_coroutine_threadsafe(_stream(), self.loop)
        except RuntimeError as exc:
            logging.error(f'Failed to start throughput stream: {exc}')
            return None

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
