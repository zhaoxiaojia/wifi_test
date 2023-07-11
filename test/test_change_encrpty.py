# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_change_encrpty.py
# Time       ：2023/7/11 14:55
# Author     ：chao.li
# version    ：python 3.6
# Description：
"""

import time

import pytest

from .. import Router
from tools.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.连接ssid
2.改变信道
3.播放youtube
重复1-3
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = '12345678'
router_open = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='36', bandwidth='20 MHz',
                     authentication_method='Open System')
router_wpa = Router(band='5 GHz', ssid=ssid, wireless_mode='Legacy', channel='40', bandwidth='20 MHz',
                    authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_wpa2 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='44', bandwidth='20 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()


@pytest.fixture(autouse=True, scope='session')
def setup():
    ax88uControl.change_setting(router_wpa)
    pytest.executer.connect_ssid(ssid,passwd)
    pytest.executer.wait_for_wifi_address()
    yield
    ax88uControl.router_control.driver.quit()
    pytest.executer.forget_network_ssid(ssid)
    pytest.executer.kill_tvsetting()


def test_change_ap():
    for i in [router_open, router_wpa, router_wpa2] * 1000:
        try:
            ax88uControl.change_setting(i)
            # time.sleep(1)
            # if i == router_open:
            #     connect_ssid(ssid)
            # else:
            #     connect_ssid(ssid, passwd)
            pytest.executer.wait_for_wifi_address()
        except Exception as e:
            ...
