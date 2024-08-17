#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_2g_switch_5g.py
# Time       ：2023/7/25 15:40
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import time

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.ZTEax5400Control import ZTEax5400Control

'''
测试步骤
2.4G和5G网络切换

1.DUT connect AP1-2.4G
2.DUT connect AP2-5G
3.Switch wifi between AP1-2.4G and AP2-5G

3.Can Play online video
'''

passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid='ATC_ASUS_AX88U_2G', wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_5g = Router(band='5 GHz', ssid='ZTEax5400_5G', wireless_mode='802.11 a/n/ac', channel='161',
                   bandwidth='20MHz/40MHz/80MHz',
                   authentication_method='WPA-PSK/WPA2-PSK', wpa_passwd='12345678')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    xiaomiControl = ZTEax5400Control()
    ax88uControl.change_setting(router_2g)
    # ax88uControl.router_control.driver.quit()
    time.sleep(1)
    xiaomiControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    xiaomiControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd()
    pytest.executer.kill_setting()


@pytest.mark.mul_router
def test_2g_switch_5g():
    assert pytest.executer.connect_ssid('ATC_ASUS_AX88U_2G', passwd), "Can't connect"
    assert pytest.executer.connect_ssid('ZTEax5400_5G', passwd), "Can't connect"
    assert pytest.executer.connect_save_ssid('ATC_ASUS_AX88U_2G'), "Can't connect"
    pytest.executer.playback_youtube()
