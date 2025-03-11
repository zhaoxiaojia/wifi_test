# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/25 15:46
# @Author  : chao.li
# @File    : test_demo.py

import logging
import pytest
import csv
from tools.router_tool.Router import Router

power_ctrl = [('192.168.200.1', '1'), ('192.168.200.3', '3')]


@pytest.fixture(scope='module', autouse=True, params=power_ctrl, ids=[str(i) for i in power_ctrl])
def power_setting(request):
    ip, port = request.param
    yield ip, port


@pytest.fixture(scope='module', autouse=True, params=['2.4G', '5G'], ids=['2.4G', '5G'])
def router_setting(power_setting, request):
    router = Router(ap='ASUS', band=request.param, wireless_mode='11AX', channel='default',
                    authentication_method='Open System',
                    bandwidth="40Mhz", ssid="coco is handsome",
                    expected_rate='0 0')
    yield router


@pytest.mark.dependency(name="scan")
def test_scan():
    logging.info('Testing scan')
    assert True


@pytest.mark.dependency(name="connect", depends=["scan"])
def test_conn():
    logging.info("Testing conn")
    assert True


@pytest.mark.dependency(depends=["connect"])
def test_multi_throughtput_tx(request):
    tx_result = "100Mb/s"
    request.node._store['return_value'] = tx_result


@pytest.mark.dependency(depends=["connect"])
@pytest.mark.wifi_connect
def test_multi_throughtput_rx(request):
    rx_result = "100Mb/s"
    request.node._store['return_value'] = rx_result
