# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_switch_2g_channel.py
# Time       ：2023/9/20 9:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import time

import pytest

from Router import Router
from tools.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.连接ssid
2.改变信道
重复1-2
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345678'
router_ch1 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='20 MHz',
                    authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_ch6 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='6', bandwidth='20 MHz',
                    authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_ch11 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='11', bandwidth='20 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()


@pytest.fixture(autouse=True, scope='session')
def teardown():
    yield
    ax88uControl.router_control.driver.quit()
    pytest.executer.forget_network_ssid(ssid)
    pytest.executer.kill_setting()


@pytest.fixture(autouse=True, params=[router_ch1, router_ch6, router_ch11] * 10000)
def setup(request):
    ax88uControl.change_setting(request.param)


def test_change_2g_channel():
    pytest.executer.connect_ssid(ssid, passwd)
