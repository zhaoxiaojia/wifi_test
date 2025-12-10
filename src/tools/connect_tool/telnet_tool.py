"""
This module implements telnet tool functionality for the connect_tool package.

It defines functions and classes used by the test harness to interface with devices and utilities.
"""

import logging
import os.path
import re
import subprocess
import time
import weakref
from contextlib import suppress
from threading import Thread
from typing import Tuple
import pytest
import asyncio
import telnetlib3
from src.tools.connect_tool.dut import dut
from src.tools.connect_tool.telnet_common import FastNegotiationTelnetClient
from src.util.constants import DEFAULT_CONNECT_MINWAIT, DEFAULT_CONNECT_MAXWAIT, get_telnet_connect_window
from typing import Annotated
from src.tools.config_loader import load_config

def _get_connect_wait_window() -> Tuple[float, float]:
    """
    Retrieve connect wait window.

    -------------------------
    It logs information for debugging or monitoring purposes.

    -------------------------
    Returns
    -------------------------
    Tuple[float, float]
        A value of type ``Tuple[float, float]``.
    """

    try:
        cfg = load_config()
    except Exception as exc:  # pragma: no cover - triggered when configuration is corrupt
        logging.debug("Failed to load configuration, using default telnet handshake wait: %s", exc)
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
            "Invalid telnet connect_minwait/connect_maxwait configuration: %r/%r, falling back to defaults",
            minwait,
            maxwait,
        )
        return DEFAULT_CONNECT_MINWAIT, DEFAULT_CONNECT_MAXWAIT

    if minwait_val < 0:
        logging.warning("telnet connect_minwait %.3f is less than 0, clamped to 0", minwait_val)
        minwait_val = 0.0

    if maxwait_val < minwait_val:
        logging.warning(
            "telnet connect_maxwait %.3f is less than connect_minwait %.3f, adjusted to the same value",
            maxwait_val,
            minwait_val,
        )
        maxwait_val = minwait_val

    return minwait_val, maxwait_val

class telnet_tool(dut):
    """
    Telnet tool.

    -------------------------
    It runs shell commands on the target device using ADB helpers and captures the output.
    It executes external commands via Python's subprocess module.
    It logs information for debugging or monitoring purposes.
    It ensures the device has root privileges when required.
    It remounts the device's file system with write permissions.

    -------------------------
    Returns
    -------------------------
    None
        This class does not return a value.
    """

    def __init__(self, dut_ip):
        """
        Init.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        dut_ip : Any
            The ``dut_ip`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        super().__init__()
        self.dut_ip = dut_ip
        self.port = 23
        self._connect_minwait, self._connect_maxwait = get_telnet_connect_window()
        self._client_factory = FastNegotiationTelnetClient
        logging.debug(
            "Telnet handshake wait window: min=%ss max=%ss",
            self._connect_minwait,
            self._connect_maxwait,
        )
        logging.info('Telnet target: %s:%s', self.dut_ip, self.port)

    async def wait_reconnect(self, timeout: int = 30, interval: float = 1.0) -> bool:
        """
        Wait for reconnect.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        timeout : Any
            Timeout in seconds for waiting or connection operations.
        interval : Any
            The ``interval`` parameter.

        -------------------------
        Returns
        -------------------------
        bool
            A value of type ``bool``.
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
        """
        Wait for reconnect sync.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        timeout : Any
            Timeout in seconds for waiting or connection operations.
        interval : Any
            The ``interval`` parameter.

        -------------------------
        Returns
        -------------------------
        bool
            A value of type ``bool``.
        """
        logging.debug(
            "Synchronously waiting for telnet reconnect to %s:%s", self.dut_ip, self.port
        )
        return asyncio.run(self.wait_reconnect(timeout=timeout, interval=interval))

    def checkoutput(self, cmd, wildcard=''):
        """
        Checkoutput.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Parameters
        -------------------------
        cmd : Any
            Command string to parse or execute.
        wildcard : Any
            The ``wildcard`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
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
        """
        Telnet client.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        command : Any
            The ``command`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """

        async def read_all(reader, timeout=2):
            """
            Read all.

            -------------------------
            Parameters
            -------------------------
            reader : Any
                The ``reader`` parameter.
            timeout : Any
                Timeout in seconds for waiting or connection operations.

            -------------------------
            Returns
            -------------------------
            Any
                The result produced by the function.
            """
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
                writer.write(command + "\n")
                await writer.drain()

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
        """
        Popen term.

        -------------------------
        It executes external commands via Python's subprocess module.

        -------------------------
        Parameters
        -------------------------
        command : Any
            The ``command`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        return subprocess.Popen(command.split(), stdout=subprocess.Pdut_ipE, stderr=subprocess.Pdut_ipE)

    def subprocess_run(self, cmd):
        """
        Subprocess run.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.
        It executes external commands via Python's subprocess module.

        -------------------------
        Parameters
        -------------------------
        cmd : Any
            Command string to parse or execute.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        return self.checkoutput(cmd)

    def root(self):
        """
        Root.

        -------------------------
        It ensures the device has root privileges when required.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        ...

    def remount(self):
        """
        Remount.

        -------------------------
        It remounts the device's file system with write permissions.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        ...

    def getprop(self, key):
        """
        Getprop.

        -------------------------
        It runs shell commands on the target device using ADB helpers and captures the output.

        -------------------------
        Parameters
        -------------------------
        key : Any
            Key identifier for sending input events.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        return self.checkoutput('getprop %s' % key)

    def get_mcs_tx(self):
        """
        Retrieve mcs tx.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        return 'mcs_tx'

    def get_mcs_rx(self):
        """
        Retrieve mcs rx.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        return 'mcs_rx'
