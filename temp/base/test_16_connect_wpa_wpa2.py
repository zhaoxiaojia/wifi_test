#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_16_connect_wpa_wpa2.py
# Time       ：2023/7/13 16:59
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试步骤
添加安全性选择 加密方式-WPA/WPA2-Personal的网络
'''
ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication='WPA/WPA2-Personal', wpa_passwd=passwd,protect_frame='停用')

@pytest.mark.wifi_connect
@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()


def test_connect_wpa_wpa2():
    pytest.dut.connect_ssid_via_ui(ssid, passwd)

