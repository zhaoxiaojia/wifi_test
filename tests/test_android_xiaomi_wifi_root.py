from unittest.mock import Mock

import pytest

import src.tools.connect_tool.duts.android as android_module
from src.tools.connect_tool.duts.android import android


@pytest.mark.parametrize('customer', ['XIAOMI', 'A', 'Roku', 'xiaomi'])
def test_xiaomi_dut_roots_before_wifi_connect(monkeypatch, customer):
    device = android.__new__(android)
    events = []
    device.root = Mock(side_effect=lambda: events.append('root'))
    device.checkoutput = Mock(side_effect=lambda command: events.append(command))
    device.wifi_wait_ip = Mock(return_value=(True, '192.168.1.2'))
    monkeypatch.setattr(android_module, 'load_config', lambda **kwargs: {'project': {'customer': customer}}, raising=False)
    monkeypatch.setattr(android_module.time, 'sleep', lambda _: None)

    assert device._android_connect_wifi('test-ssid', '', 'open', False, lan=False)

    command = device.CMD_WIFI_CONNECT.format('test-ssid', 'open', '')
    assert events == (['root', command] if customer == 'XIAOMI' else [command])
