# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_switch_5g_channel.py
# Time       ：2023/9/20 13:55
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

ssid = 'ATC_ASUS_AX88U_5G'
passwd = '12345678'
router_ch36 = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='36', bandwidth='20 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_ch48 = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='48', bandwidth='20 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_ch149 = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='149', bandwidth='20 MHz',
                      authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()


@pytest.fixture(autouse=True, scope='session')
def teardown():
    yield
    logging.info('handsome')
    ax88uControl.router_control.driver.quit()
    pytest.executer.forget_network_ssid(ssid)
    pytest.executer.kill_tvsetting()


@pytest.fixture(autouse=True, params=[router_ch36, router_ch48, router_ch149] * 10000)
def setup(request):
    ax88uControl.change_setting(request.param)


def test_change_5g_channel():
    pytest.executer.connect_ssid(ssid, passwd)
