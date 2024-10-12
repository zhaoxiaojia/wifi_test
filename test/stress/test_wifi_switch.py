# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/12 13:50
# @Author  : chao.li
# @File    : test_wifi_switch.py
import logging
import time
from test.stress import multi_stress

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='Open System')


# @pytest.mark.wifi_connect
# @pytest.fixture(autouse=True)
# def setup_teardown():
#     ax88uControl = Asusax88uControl()
#     ax88uControl.change_setting(router_2g)
#     ax88uControl.router_control.driver.quit()
#     time.sleep(10)
#     yield
#     pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
#     pytest.dut.kill_setting()


@multi_stress
def test_wiif_switch(device):
    # device.checkoutput(device.CMD_WIFI_CONNECT.format(ssid, 'open', ''))
    # device.wait_for_wifi_address()
    start_time = time.time()
    while time.time() - start_time < 3600 * 12:
        device.checkoutput(device.SVC_WIFI_DISABLE)
        time.sleep(2)
        device.checkoutput(device.SVC_WIFI_ENABLE)
        time.sleep(2)
