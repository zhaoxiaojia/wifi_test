# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/12 13:50
# @Author  : chao.li
# @File    : test_wifi_switch.py

import time
from src.test import multi_stress

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4G', ssid=ssid, wireless_mode='11n', channel='1', bandwidth='40 MHz',
                   authentication='Open System')

'''
Test step
1.Connect any AP
2.Do wifi on/off stress test for about 12 hours.
3.Check wifi status

Expected Result
3.WIFI works well,AP list display normal.

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
def test_wifi_switch(device):
    device.checkoutput(device.CMD_WIFI_CONNECT.format(ssid, 'open', ''))
    device.wait_for_wifi_address()
    start_time = time.time()
    while time.time() - start_time < 3600 * 12:
        device.checkoutput(device.SVC_WIFI_DISABLE)
        time.sleep(2)
        device.checkoutput(device.SVC_WIFI_ENABLE)
        time.sleep(2)
