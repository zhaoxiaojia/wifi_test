#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_15_connect_open.py
# Time       ：2023/7/13 16:53
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import time

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

'''
测试步骤
添加安全性选择 加密方式-开放的网络
'''
ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='Open System')


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


def test_connect_open():
    pytest.dut.connect_ssid_via_ui(ssid)
    assert pytest.dut.wait_for_wifi_address(), "Connect fail"
