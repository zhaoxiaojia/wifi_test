# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_switch_authentication.py
# Time       ：2023/10/9 9:57
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.连接ssid
2.改变信道
重复1-2
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = '12345678'
router_open = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='36', bandwidth='40 MHz',
                     authentication_method='Open System')
router_legacy = Router(band='5 GHz', ssid=ssid, wireless_mode='Legacy', channel='40', bandwidth='20 MHz',
                       authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_auto = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='44', bandwidth='40 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()


@pytest.fixture(autouse=True, scope='session')
def teardown():
    yield
    ax88uControl.router_control.driver.quit()
    pytest.executer.forget_network_ssid(ssid)
    pytest.executer.kill_setting()


@pytest.fixture(autouse=True, params=[router_open, router_legacy, router_auto] * 10000)
def setup(request):
    ax88uControl.change_setting(request.param)


def test_change_5g_authentication():
    pytest.executer.connect_ssid(ssid, passwd)
