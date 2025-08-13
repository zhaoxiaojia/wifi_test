# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/14 9:24
# @Author  : chao.li
# @File    : test_ap_switch.py


import time
from src.test import multi_stress

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

ssid_2g = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid_2g, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication='Open System')
ssid_5g = 'ATC_ASUS_AX88U_5G'
router_5g = Router(band='5 GHz', ssid=ssid_5g, wireless_mode='自动', channel='149', bandwidth='20/40/80 MHz',
                   authentication='Open System')
'''
Test step
1.Connect a 2.4G AP.
2.Connect a 5G AP.
3.Do switch AP connection test for about 12 hours.
4.Check wifi status

Expected Result
4.WIFI works well,AP list display normal.

'''


@pytest.mark.wifi_connect
@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    time.sleep(10)
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()


@multi_stress
def test_ap_switch(device):
    start_time = time.time()
    while time.time() - start_time < 3600 * 12:
        device.checkoutput(device.CMD_WIFI_CONNECT.format(ssid_2g, 'open', ''))
        device.wait_for_wifi_address()
        device.checkoutput(device.CMD_WIFI_CONNECT.format(ssid_5g, 'open', ''))
        device.wait_for_wifi_address()
