# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/19 13:36
# @Author  : Chao.li
# @File    : test_Wifi_forget_network.py
# @Project : python
# @Software: PyCharm


import logging
import os
import time

import pytest
from test import Router, find_ssid, wait_for_wifi_address

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.yamlTool import yamlTool

'''
测试步骤
Forget network

1.WIFI列表中存在一个Save的网络
2.点击Save的网络
3.选择Forget network

DUT不会再保存这个网络
'''

router_2g = Router(band='2.4 GHz', ssid='ATC_ASUS_AX88U_2G', wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd='12345678')


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    # connect wifi
    cmd = pytest.dut.CMD_WIFI_CONNECT.format('ATC_ASUS_AX88U_2G', 'wpa2', '12345678')
    pytest.dut.checkoutput(cmd)
    wait_for_wifi_address(cmd)
    yield


def test_forget_wifi():
    find_ssid('ATC_ASUS_AX88U_2G')
    pytest.dut.wait_and_tap('Forget network', 'text')
    for _ in range(3):
        if pytest.dut.find_element('Internet connection', 'text'):
            break
        time.sleep(1)
        pytest.dut.keyevent(23)
        pytest.dut.keyevent(23)
    pytest.dut.uiautomator_dump()
    while 'Not connected' not in pytest.dut.get_dump_info():
        time.sleep(1)
        pytest.dut.uiautomator_dump()
    assert not pytest.dut.ping(hostname="192.168.50.1")
