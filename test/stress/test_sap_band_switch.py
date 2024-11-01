# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/14 11:15
# @Author  : chao.li
# @File    : test_sap_band_switch.py



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
2.Turn on SAP, set 2.4G.
3.Switch SAP band to 5G,then save.
4.Switch SAP band stress test for about 12 hours.

Expected Result
WIFI works well,AP list display normal.
SAP works well.

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
def test_sta_sap_switch(device):
    device.checkoutput(device.CMD_WIFI_CONNECT.format(ssid, 'open', ''))
    device.wait_for_wifi_address()
    start_time = time.time()
    while time.time() - start_time < 3600 * 12:
        device.checkoutput(device.CMD_WIFI_START_SAP.format('android_sap_2g', 'open', '', '2'))
        time.sleep(2)
        device.checkoutput(device.CMD_WIFI_START_SAP.format('android_sap_5g', 'open', '', '2'))
        time.sleep(2)
