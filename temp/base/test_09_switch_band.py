#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_09_switch_band.py
# Time       ：2023/7/13 11:10
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试步骤
1.设备连接2.4G
2.设备连接5G
3.在2.4G和5G之间进行切换连接
'''

ssid_2g = 'ATC_ASUS_AX88U_2G'
ssid_5g = 'ATC_ASUS_AX88U_5G'
passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid=ssid_2g, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)
router_5g = Router(band='5 GHz', ssid=ssid_5g, wireless_mode='N/AC/AX mixed', channel='36', bandwidth='40 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.forget_network_cmd()
    pytest.dut.kill_setting()


def test_switch_band():
    pytest.dut.connect_ssid_via_ui(ssid_2g, passwd=passwd)
    pytest.dut.kill_setting()
    pytest.dut.forget_network_cmd()
    pytest.dut.connect_ssid_via_ui(ssid_5g, passwd=passwd)
