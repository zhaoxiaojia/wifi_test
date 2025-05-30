# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/25 15:46
# @Author  : chao.li
# @File    : test_demo.py

import logging
import pytest
import csv
from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

power_ctrl = [('192.168.200.1', '1'), ('192.168.200.3', '3')]



@pytest.fixture(scope='module', autouse=True, params=power_ctrl, ids=[str(i) for i in power_ctrl])
def power_setting(request):
    ip, port = request.param
    yield ip, port




@pytest.mark.dependency(name="scan")
def test_scan(router_setting):
    result = 'PASS' if pytest.dut.wifi_scan(router_setting.ssid) else 'FAIL'
    assert result == 'PASS', f"Can't scan target ssid {router_setting.ssid}"

# @pytest.mark.dependency(name="connect", depends=["scan"])
# def test_conn():
#     logging.info("Testing conn")
#     assert True


# @pytest.mark.dependency(depends=["connect"])
# def test_multi_throughtput_tx(request):
#     tx_result = "100Mb/s"
#     request.node._store['return_value'] =(100 ,tx_result)
#
#
# @pytest.mark.dependency(depends=["connect"])
# @pytest.mark.wifi_connect
# def test_multi_throughtput_rx(request):
#     rx_result = "100Mb/s"
#     request.node._store['return_value'] =(100 ,rx_result)
