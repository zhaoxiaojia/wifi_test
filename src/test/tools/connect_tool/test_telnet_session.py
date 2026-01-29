import asyncio

import pytest

from src.tools.connect_tool.transports.telnet_tool import TelnetSession


class _DummyWriter:
    def is_closing(self) -> bool:
        return False

    def close(self) -> None:
        return None


class _DummyReader:
    def __init__(self, *, value, delay_s: float = 0.0, eof: bool = False):
        self._value = value
        self._delay_s = delay_s
        self._eof = eof

    def at_eof(self) -> bool:
        return self._eof

    async def read(self, _n: int):
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        return self._value


def _connected_session(*, reader: _DummyReader) -> TelnetSession:
    session = TelnetSession("127.0.0.1", timeout=0.1)
    session._reader = reader
    session._writer = _DummyWriter()
    session.sock = object()
    return session


def test_read_some_timeout_returns_empty_bytes():
    session = _connected_session(reader=_DummyReader(value="abc", delay_s=0.2))
    try:
        assert session.read_some(4096, timeout=0.01) == b""
    finally:
        session.close()


def test_read_some_eof_raises():
    session = _connected_session(reader=_DummyReader(value=""))
    try:
        with pytest.raises(EOFError):
            session.read_some(4096, timeout=0.1)
    finally:
        session.close()


def test_read_some_encodes_str_to_bytes():
    session = _connected_session(reader=_DummyReader(value="hello"))
    try:
        assert session.read_some(4096, timeout=0.1) == b"hello"
    finally:
        session.close()


def test_read_some_returns_bytes_unchanged():
    session = _connected_session(reader=_DummyReader(value=b"raw"))
    try:
        assert session.read_some(4096, timeout=0.1) == b"raw"
    finally:
        session.close()
