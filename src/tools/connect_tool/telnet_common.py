"""
Common telnet helpers built on top of telnetlib3.

This module provides:
    - FastNegotiationTelnetClient: a TelnetClient subclass that accelerates
      option negotiation, shared with telnet_tool and other utilities.
    - TelnetSession: a small, synchronous wrapper around telnetlib3 that
      exposes a subset of the classic telnetlib.Telnet interface
      (open/write/read_until/read_some/close) for existing sync code.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from contextlib import suppress
from typing import Optional

import telnetlib3
from telnetlib3.client import TelnetClient


class FastNegotiationTelnetClient(TelnetClient):
    """
    Telnet client that completes option negotiation as early as possible.
    """

    def begin_negotiation(self) -> None:
        super().begin_negotiation()
        _complete_negotiation_if_ready(self)

    def data_received(self, data):  # noqa: D401 reuse base class documentation
        super().data_received(data)
        _complete_negotiation_if_ready(self)

    def check_negotiation(self, final: bool = False):  # noqa: D401 reuse base class documentation
        if _negotiation_settled(self, final):
            return True
        return super().check_negotiation(final=final)


def _negotiation_settled(self, final: bool = False) -> bool:
    """
    Return True when telnet option negotiation has settled.
    """
    if self.writer is None:
        return False
    if any(self.writer.pending_option.values()):
        return False
    return final or self.duration >= self.connect_minwait


def _complete_negotiation_if_ready(self) -> None:
    """
    Mark the connection as established once negotiation is complete.
    """
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


# Attach helper functions as methods on the fast client so that
# attribute lookups used by telnetlib3 callbacks succeed even when
# the underlying TelnetClient implementation does not provide these
# helpers natively.
FastNegotiationTelnetClient._negotiation_settled = _negotiation_settled  # type: ignore[attr-defined]
FastNegotiationTelnetClient._complete_negotiation_if_ready = (  # type: ignore[attr-defined]
    _complete_negotiation_if_ready
)  # type: ignore[attr-defined]


class TelnetSession:
    """
    Synchronous wrapper around telnetlib3 with a minimal telnetlib.Telnet-like API.

    This class is intended for existing synchronous code that previously used
    telnetlib.Telnet. It keeps a dedicated asyncio event loop internally and
    exposes blocking methods that operate on a persistent telnet connection.
    """

    def __init__(
        self,
        host: str,
        port: int = 23,
        *,
        timeout: float = 10.0,
        encoding: str = "ascii",
        client_factory: Optional[type[TelnetClient]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.encoding = encoding
        self._client_factory = client_factory or FastNegotiationTelnetClient

        self._loop = asyncio.new_event_loop()
        self._reader = None
        self._writer = None
        # Exposed for compatibility with legacy telnetlib-based checks.
        self.sock = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def open(self) -> None:
        """
        Establish the telnet connection.
        """

        async def _open():
            reader, writer = await telnetlib3.open_connection(
                self.host,
                self.port,
                client_factory=self._client_factory,
            )
            return reader, writer

        if self._loop.is_closed():
            self._loop = asyncio.new_event_loop()

        try:
            reader, writer = self._loop.run_until_complete(
                asyncio.wait_for(_open(), timeout=self.timeout)
            )
        except Exception:
            logging.exception("Failed to open TelnetSession to %s:%s", self.host, self.port)
            self._reader = None
            self._writer = None
            self.sock = None
            raise

        self._reader = reader
        self._writer = writer
        # We only need a truthy object here; callers check for non-None.
        self.sock = object()

    def close(self) -> None:
        """
        Close the telnet connection and release the event loop.
        """
        if self._loop.is_closed():
            self._reader = None
            self._writer = None
            self.sock = None
            return

        async def _close():
            if self._writer is not None:
                self._writer.close()
                if hasattr(self._writer, "wait_closed"):
                    with suppress(Exception):
                        await self._writer.wait_closed()

        try:
            if self._writer is not None:
                self._loop.run_until_complete(_close())
        finally:
            self._reader = None
            self._writer = None
            self.sock = None
            try:
                self._loop.close()
            except Exception:
                # Closing an already-closed loop or one in a bad state should
                # not propagate to callers.
                logging.debug("Error closing TelnetSession event loop", exc_info=True)

    # ------------------------------------------------------------------
    # I/O helpers (telnetlib-like)
    # ------------------------------------------------------------------
    def write(self, data: bytes) -> None:
        """
        Write raw bytes to the telnet connection.
        """
        if self._writer is None:
            raise RuntimeError("TelnetSession is not connected")

        async def _write():
            text = data.decode(self.encoding, errors="ignore")
            self._writer.write(text)
            await self._writer.drain()

        self._loop.run_until_complete(_write())

    def read_some(self, size: int = 1024, timeout: Optional[float] = None) -> bytes:
        """
        Read up to ``size`` characters and return them as bytes.
        """
        if self._reader is None:
            raise RuntimeError("TelnetSession is not connected")

        async def _read():
            if timeout is not None:
                return await asyncio.wait_for(self._reader.read(size), timeout)
            return await self._reader.read(size)

        try:
            text = self._loop.run_until_complete(_read())
        except asyncio.TimeoutError:
            return b""

        if not text:
            return b""
        return text.encode(self.encoding, errors="ignore")

    def read_until(self, expected: bytes, timeout: Optional[float] = None) -> bytes:
        """
        Read until the given byte sequence is seen or timeout expires.
        """
        if self._reader is None:
            raise RuntimeError("TelnetSession is not connected")

        target = expected.decode(self.encoding, errors="ignore")

        async def _read_until():
            buf = ""
            while True:
                try:
                    if timeout is not None:
                        chunk = await asyncio.wait_for(self._reader.read(1), timeout)
                    else:
                        chunk = await self._reader.read(1)
                except asyncio.TimeoutError:
                    # Overall timeout for this read_until call; return
                    # whatever has been collected so far (which may be
                    # an empty string).
                    return buf, False
                if not chunk:
                    # Remote closed the connection.
                    return buf, True
                buf += chunk
                if buf.endswith(target):
                    return buf, False

        text, eof = self._loop.run_until_complete(_read_until())
        if eof and not text:
            # Match telnetlib behaviour where read_until raises EOFError
            # when the connection is closed and no data is returned.
            raise EOFError("TelnetSession connection closed")
        if not text:
            return b""
        return text.encode(self.encoding, errors="ignore")

