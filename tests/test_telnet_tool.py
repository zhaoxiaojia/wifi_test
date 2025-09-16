"""针对 telnet 工具在高负载场景下的行为进行验证。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# 将项目根目录加入 sys.path，方便导入 ``src`` 包
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tools.connect_tool.telnet_tool import telnet_tool  # noqa: E402
from src.tools.connect_tool.dut import dut  # noqa: E402
import src.tools.connect_tool.dut as dut_module  # noqa: E402


class _SlowReader:
    """模拟 Telnet 在高负载下需要更长时间才返回数据。"""

    def __init__(self, payload: str, delay: float) -> None:
        self._payload = payload
        self._delay = delay
        self._delivered = False

    async def read(self, _n: int) -> str:
        if not self._delivered:
            await asyncio.sleep(self._delay)
            self._delivered = True
            return self._payload
        return ""


class _DummyWriter:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def write(self, data: str) -> None:
        self.commands.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:  # pragma: no cover - 仅用于匹配真实对象接口
        return None


def test_checkoutput_waits_for_delayed_iw_link() -> None:
    """当输出延迟超过 2 秒时，依然能够完整获取 `iw dev wlan0 link` 的回显。"""

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    tool = telnet_tool("127.0.0.1")
    tool.loop = loop
    tool.reader = _SlowReader(
        "Connected to 00:11:22:33:44:55\nfreq: 5180\nsignal: -60 dBm\n", delay=2.1
    )
    tool.writer = _DummyWriter()

    output = tool.checkoutput("iw dev wlan0 link")

    assert "signal: -60 dBm" in output
    assert tool.writer.commands[-1] == "iw dev wlan0 link\n"

    tool.close()
    asyncio.set_event_loop(None)


def test_get_rssi_parses_signal_under_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 `dut.get_rssi` 能在多次尝试后解析出信号强度。"""

    iw_output = (
        "Connected to 00:11:22:33:44:55\n"
        "SSID: TestWiFi\n"
        "freq: 5180\n"
        "signal: -45 dBm\n"
    )

    class _RetryTelnet:
        IW_LINNK_COMMAND = "iw dev wlan0 link"

        def __init__(self) -> None:
            self.calls = 0

        def checkoutput(self, cmd: str, wildcard: str = "") -> str:
            assert cmd == self.IW_LINNK_COMMAND
            self.calls += 1
            if self.calls < 3:
                return ""
            return iw_output

    fake_telnet = _RetryTelnet()

    import pytest as pytest_module

    monkeypatch.setattr(pytest_module, "dut", fake_telnet, raising=False)
    monkeypatch.setattr(dut_module.time, "sleep", lambda *_: None)

    device = dut()
    result = device.get_rssi()

    assert result == -45
    assert device.freq_num == 5180
    assert fake_telnet.calls == 3
