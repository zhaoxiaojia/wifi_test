#!/usr/bin/env python 
# -*- coding: utf-8 -*- 


"""
# File       : telnet_tool.py
# Time       ：2023/6/30 16:57
# Author     ：chao.li
# version    ：python 3.9
# Descrdut_iption：
"""

import logging
import os.path
import re
import subprocess
import telnetlib
import time
import weakref
from contextlib import suppress
from threading import Thread
from typing import Tuple
import pytest
import asyncio
import telnetlib3
from telnetlib3.client import TelnetClient
from src.tools.connect_tool.dut import dut
from src.util.constants import DEFAULT_CONNECT_MINWAIT, DEFAULT_CONNECT_MAXWAIT, get_telnet_connect_window



def _get_connect_wait_window() -> Tuple[float, float]:
    """读取 telnet 连接等待窗口配置。"""

    try:
        cfg = load_config()
    except Exception as exc:  # pragma: no cover - 仅在配置损坏时触发
        logging.debug("加载配置失败，使用默认 telnet 握手等待：%s", exc)
        return DEFAULT_CONNECT_MINWAIT, DEFAULT_CONNECT_MAXWAIT

    connect_cfg = cfg.get("connect_type", {}) or {}
    telnet_cfg = connect_cfg.get("Linux") or connect_cfg.get("telnet") or {}

    minwait = telnet_cfg.get("connect_minwait", DEFAULT_CONNECT_MINWAIT)
    maxwait = telnet_cfg.get("connect_maxwait", DEFAULT_CONNECT_MAXWAIT)

    try:
        minwait_val = float(minwait)
        maxwait_val = float(maxwait)
    except (TypeError, ValueError):
        logging.warning(
            "telnet connect_minwait/connect_maxwait 配置无效：%r/%r，退回默认值",
            minwait,
            maxwait,
        )
        return DEFAULT_CONNECT_MINWAIT, DEFAULT_CONNECT_MAXWAIT

    if minwait_val < 0:
        logging.warning("telnet connect_minwait %.3f 小于 0，已钳制为 0", minwait_val)
        minwait_val = 0.0

    if maxwait_val < minwait_val:
        logging.warning(
            "telnet connect_maxwait %.3f 小于 connect_minwait %.3f，已调整为相同值",
            maxwait_val,
            minwait_val,
        )
        maxwait_val = minwait_val

    return minwait_val, maxwait_val


class FastNegotiationTelnetClient(TelnetClient):
    """快速确认握手状态的 Telnet 客户端。"""

    def begin_negotiation(self):
        super().begin_negotiation()
        self._complete_negotiation_if_ready()

    def data_received(self, data):  # noqa: D401 复用基类文档
        super().data_received(data)
        self._complete_negotiation_if_ready()

    def check_negotiation(self, final=False):  # noqa: D401 复用基类文档
        if self._negotiation_settled(final):
            return True
        return super().check_negotiation(final=final)

    def _negotiation_settled(self, final=False) -> bool:
        if self.writer is None:
            return False
        if any(self.writer.pending_option.values()):
            return False
        return final or self.duration >= self.connect_minwait

    def _complete_negotiation_if_ready(self):
        if self._waiter_connected.done():
            return
        if not self._negotiation_settled():
            return

        check_later = getattr(self, "_check_later", None)
        if check_later is not None:
            check_later.cancel()
            with suppress(ValueError):
                self._tasks.remove(check_later)

        self._waiter_connected.set_result(weakref.proxy(self))


class telnet_tool(dut):
    def __init__(self, dut_ip):
        super().__init__()
        self.dut_ip = dut_ip
        self.port = 23
        self._connect_minwait, self._connect_maxwait = get_telnet_connect_window()
        self._client_factory = FastNegotiationTelnetClient
        logging.debug(
            "telnet 握手等待窗口：min=%ss max=%ss",
            self._connect_minwait,
            self._connect_maxwait,
        )
        logging.info('Telnet target: %s:%s', self.dut_ip, self.port)

    async def wait_reconnect(self, timeout: int = 30, interval: float = 1.0) -> bool:
        """等待 Telnet 连接恢复。

        :param timeout: 超时时间（秒）。
        :param interval: 每次重试前的等待时间（秒）。
        :return: 连接成功返回 True，否则返回 False。
        """
        if timeout <= 0:
            logging.error(
                "Invalid timeout %.2f when waiting for telnet reconnect to %s:%s",
                timeout,
                self.dut_ip,
                self.port,
            )
            return False

        logging.debug(
            "Waiting for telnet reconnect to %s:%s (timeout=%ss, interval=%ss)",
            self.dut_ip,
            self.port,
            timeout,
            interval,
        )

        start_time = time.monotonic()
        attempt = 0
        last_error = None

        while True:
            attempt += 1
            elapsed = time.monotonic() - start_time
            if elapsed >= timeout:
                break

            remaining = timeout - elapsed
            logging.debug(
                "Telnet reconnect attempt %d to %s:%s (remaining %.2fs)",
                attempt,
                self.dut_ip,
                self.port,
                remaining,
            )

            try:
                _reader, writer = await asyncio.wait_for(
                    telnetlib3.open_connection(self.dut_ip, self.port),
                    timeout=remaining,
                )
                logging.debug(
                    "Telnet connection to %s:%s re-established on attempt %d",
                    self.dut_ip,
                    self.port,
                    attempt,
                )

                if writer:
                    writer.close()
                    wait_closed = getattr(writer, "wait_closed", None)
                    if callable(wait_closed):
                        try:
                            await wait_closed()
                        except Exception as close_error:
                            logging.debug(
                                "Ignored error while closing telnet writer: %s",
                                close_error,
                            )
                return True
            except asyncio.CancelledError:
                logging.warning(
                    "Telnet reconnect wait cancelled for %s:%s on attempt %d",
                    self.dut_ip,
                    self.port,
                    attempt,
                )
                raise
            except (asyncio.TimeoutError, ConnectionError, OSError) as error:
                last_error = error
                logging.warning(
                    "Telnet reconnect attempt %d to %s:%s failed: %s",
                    attempt,
                    self.dut_ip,
                    self.port,
                    error,
                )
            except Exception as error:
                last_error = error
                logging.exception(
                    "Unexpected error when attempting to reconnect telnet to %s:%s",
                    self.dut_ip,
                    self.port,
                )

            remaining = timeout - (time.monotonic() - start_time)
            if remaining <= 0:
                break

            sleep_time = min(max(interval, 0), remaining)
            logging.debug(
                "Sleeping %.2fs before next telnet reconnect attempt (remaining %.2fs)",
                sleep_time,
                remaining - sleep_time,
            )
            await asyncio.sleep(sleep_time)

        logging.error(
            "Failed to re-establish telnet connection to %s:%s within %.2fs. Last error: %s",
            self.dut_ip,
            self.port,
            timeout,
            last_error,
        )
        return False

    def wait_reconnect_sync(self, timeout: int = 30, interval: float = 1.0) -> bool:
        """同步等待 Telnet 连接恢复。"""
        logging.debug(
            "Synchronously waiting for telnet reconnect to %s:%s", self.dut_ip, self.port
        )
        return asyncio.run(self.wait_reconnect(timeout=timeout, interval=interval))

    def checkoutput(self, cmd, wildcard=''):
        connection_errors = (ConnectionError, OSError, asyncio.TimeoutError, RuntimeError)
        try:
            return asyncio.run(self.telnet_client(cmd))
        except connection_errors:
            if not self.wait_reconnect_sync():
                raise ConnectionError(
                    f"Failed to establish telnet connection to {self.dut_ip}:{self.port} before executing command"
                )
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

        max_attempts = 3
        retryable_exceptions = (asyncio.TimeoutError, ConnectionError, OSError)

        for attempt in range(1, max_attempts + 1):
            reader = writer = None
            try:
                reader, writer = await telnetlib3.open_connection(
                    self.dut_ip,
                    self.port,
                    client_factory=self._client_factory,
                    connect_minwait=self._connect_minwait,
                    connect_maxwait=self._connect_maxwait,
                )
                # 发送命令
                writer.write(command + "\n")
                await writer.drain()

                # 读取命令执行结果
                result = await read_all(reader)
                return result
            except asyncio.CancelledError:
                raise
            except retryable_exceptions as exc:
                logging.warning(
                    "Telnet attempt %s/%s failed with retryable error %s: %s",
                    attempt,
                    max_attempts,
                    exc.__class__.__name__,
                    exc,
                )
            except Exception as exc:
                logging.error(
                    "Telnet attempt %s/%s failed with non-retryable error %s: %s",
                    attempt,
                    max_attempts,
                    exc.__class__.__name__,
                    exc,
                )
                raise
            finally:
                if writer is not None:
                    try:
                        writer.close()
                    except Exception as close_exc:
                        logging.debug(
                            "Error closing telnet writer after attempt %s: %s",
                            attempt,
                            close_exc,
                        )
                    if hasattr(writer, "wait_closed"):
                        try:
                            await writer.wait_closed()
                        except Exception as close_exc:
                            logging.debug(
                                "Error waiting for telnet writer to close after attempt %s: %s",
                                attempt,
                                close_exc,
                            )

        raise RuntimeError(
            f"Telnet command '{command}' failed without raising expected exception"
        )

    def popen_term(self, command):
        return subprocess.Popen(command.split(), stdout=subprocess.Pdut_ipE, stderr=subprocess.Pdut_ipE)

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
