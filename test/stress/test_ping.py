# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/21 11:02
# @Author  : chao.li
# @File    : test_ping.py


import logging
import time
from test.stress import multi_stress

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='11n', channel='1', bandwidth='40 MHz',
                   authentication_method='Open System')

'''
Test step
1.Connect any AP
2.Ping IP 100000 times
3.Check wifi status

Expected Result
WIFI works well,AP list display normal.

'''


@pytest.mark.wifi_connect
@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    time.sleep(10)
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()


@multi_stress
def test_ping(device):
    device.checkoutput(device.CMD_WIFI_CONNECT.format(ssid, 'open', ''))
    device.wait_for_wifi_address()
    device.checkoutput(device.CMD_PING.format(100000))
    time.sleep(2)
