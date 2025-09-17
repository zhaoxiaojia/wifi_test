import asyncio
import sys
import types
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda *_args, **_kwargs: {}))

from src.tools.connect_tool import telnet3_tool as telnet_module
from src.tools.connect_tool import telnet_tool as sync_telnet_module


class FakeReader:
    def __init__(self, eof_after_empty=False):
        self._queue: list[str] = []
        self._at_eof = False
        self._eof_after_empty = eof_after_empty

    def queue_response(self, response: str) -> None:
        self._queue.append(response)
        self._at_eof = False

    async def read(self, _: int) -> str:
        if self._queue:
            return self._queue.pop(0)
        if self._eof_after_empty:
            self._at_eof = True
        await asyncio.sleep(0)
        return ""

    def at_eof(self) -> bool:
        return self._at_eof


class FakeWriter:
    def __init__(self, reader: FakeReader, responses: list[str], *, drain_side_effects=None, closing=False):
        self.reader = reader
        self.responses = responses
        self._write_count = 0
        self._drain_side_effects = list(drain_side_effects or [])
        self._closing_flag = closing
        self.commands: list[str] = []

    def write(self, data: str) -> None:
        self.commands.append(data.rstrip())
        index = min(self._write_count, len(self.responses) - 1) if self.responses else None
        if index is not None and index >= 0:
            self.reader.queue_response(self.responses[index])
        else:
            self.reader.queue_response("")
        self._write_count += 1

    async def drain(self) -> None:
        if self._drain_side_effects:
            effect = self._drain_side_effects.pop(0)
            if effect:
                self._closing_flag = True
                raise effect
        await asyncio.sleep(0)

    def is_closing(self) -> bool:
        return self._closing_flag

    def close(self) -> None:
        self._closing_flag = True


class FakeTelnetConnection:
    def __init__(self, *, responses, eof_after=False, drain_side_effects=None, closing=False):
        self.reader = FakeReader(eof_after_empty=eof_after)
        self.writer = FakeWriter(
            self.reader,
            list(responses),
            drain_side_effects=drain_side_effects,
            closing=closing,
        )


class FakeTelnetFactory:
    def __init__(self, connections):
        self._connections = list(connections)
        self.call_count = 0

    async def open_connection(self, ip, port):
        assert ip
        assert port
        if not self._connections:
            raise AssertionError("No fake connections left")
        self.call_count += 1
        conn = self._connections.pop(0)
        return conn.reader, conn.writer


@pytest.fixture()
def fake_telnet(monkeypatch):
    factory = FakeTelnetFactory([])

    def set_connections(connections):
        factory._connections = list(connections)

    monkeypatch.setattr(
        telnet_module,
        "telnetlib3",
        types.SimpleNamespace(open_connection=factory.open_connection),
    )
    return factory, set_connections


def test_telnet_repeated_get_rssi(fake_telnet):
    factory, set_connections = fake_telnet
    set_connections(
        [
            FakeTelnetConnection(
                responses=["signal: -50 dBm", "signal: -55 dBm"],
            )
        ]
    )
    tool = telnet_module.Telnet3Tool("127.0.0.1")
    try:
        first = tool.checkoutput("iw dev wlan0 link")
        second = tool.checkoutput("iw dev wlan0 link")
    finally:
        tool.close()
    assert first == "signal: -50 dBm"
    assert second == "signal: -55 dBm"
    assert factory.call_count == 1


def test_telnet_reconnects_when_reader_hits_eof(fake_telnet):
    factory, set_connections = fake_telnet
    set_connections(
        [
            FakeTelnetConnection(responses=["round-one"], eof_after=True),
            FakeTelnetConnection(responses=["round-two"]),
        ]
    )
    tool = telnet_module.Telnet3Tool("127.0.0.1")
    try:
        first = tool.checkoutput("iw dev wlan0 link")
        second = tool.checkoutput("iw dev wlan0 link")
    finally:
        tool.close()
    assert first == "round-one"
    assert second == "round-two"
    assert factory.call_count == 2


def test_telnet_retry_on_connection_reset(fake_telnet):
    factory, set_connections = fake_telnet
    set_connections(
        [
            FakeTelnetConnection(
                responses=["should-not-return"],
                drain_side_effects=[ConnectionResetError("reset once")],
            ),
            FakeTelnetConnection(responses=["iperf done"]),
        ]
    )
    tool = telnet_module.Telnet3Tool("127.0.0.1")
    try:
        result = tool.checkoutput("iperf -c 192.168.1.1")
    finally:
        tool.close()
    assert result == "iperf done"
    assert factory.call_count == 2


def test_telnet_retry_on_runtime_error(fake_telnet):
    factory, set_connections = fake_telnet
    set_connections(
        [
            FakeTelnetConnection(
                responses=["ignored"],
                drain_side_effects=[RuntimeError("Event loop is closed")],
            ),
            FakeTelnetConnection(responses=["retry ok"]),
        ]
    )
    tool = telnet_module.Telnet3Tool("127.0.0.1")
    try:
        result = tool.checkoutput("iperf -c 192.168.1.1")
    finally:
        tool.close()
    assert result == "retry ok"
    assert factory.call_count == 2


def test_sync_telnet_checkoutput_reads_until_quiet(monkeypatch):
    responses = [b"", b"signal: -42 dBm\n", b""]

    class DummyTelnet:
        def __init__(self):
            self.responses = list(responses)
            self.sock = object()
            self.write_history = []

        def close(self):
            self.sock = None

        def read_very_eager(self):
            return self.responses.pop(0) if self.responses else b""

        def write(self, data: bytes):
            self.write_history.append(data)

        def read_until(self, expected, timeout=None):
            return self.read_very_eager()

    dummy = DummyTelnet()

    def fake_telnet(*_args, **_kwargs):
        dummy.responses = list(responses)
        dummy.write_history.clear()
        dummy.sock = object()
        return dummy

    monkeypatch.setattr(sync_telnet_module, "telnetlib", types.SimpleNamespace(Telnet=fake_telnet))

    tool = sync_telnet_module.TelnetTool("127.0.0.1", timeout=0.05)
    try:
        output = tool.checkoutput("iw dev wlan0 link")
    finally:
        tool.close()

    assert output == "signal: -42 dBm"
    assert dummy.write_history[-1] == b"iw dev wlan0 link\n"
