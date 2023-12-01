#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_09_switch_band.py
# Time       ：2023/7/13 11:10
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import re
import time

import pytest

from Router import Router
from tools.Asusax88uControl import Asusax88uControl

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
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_5g = Router(band='5 GHz', ssid=ssid_5g, wireless_mode='N/AC/AX mixed', channel='36', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd()
    pytest.executer.kill_setting()


def test_switch_band():
    pytest.executer.connect_ssid(ssid_2g,passwd=passwd)
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd()
    pytest.executer.connect_ssid(ssid_5g,passwd=passwd)
