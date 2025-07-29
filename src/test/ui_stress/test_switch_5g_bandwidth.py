# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_switch_5g_bandwidth.py
# Time       ：2023/9/20 14:53
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试步骤
1.连接ssid
2.改变带宽
重复1-2
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = '12345678'
router_bd20 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='36', bandwidth='20 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_bd40 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='36', bandwidth='40 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_bd80 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='36', bandwidth='80 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_bdmix = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='36', bandwidth='20/40/80 MHz',
                      authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()


@pytest.fixture(autouse=True, scope='session')
def teardown():
    yield
    ax88uControl.router_control.driver.quit()
    pytest.dut.forget_network_ssid(ssid)
    pytest.dut.kill_setting()


@pytest.fixture(autouse=True, params=[router_bd20, router_bd40, router_bd80, router_bdmix] * 10000)
def setup(request):
    ax88uControl.change_setting(request.param)


def test_change_5g_bandwidth():
    pytest.dut.connect_ssid_via_ui(ssid, passwd)
