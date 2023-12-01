# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_check_2g_saved_status.py
# Time       ：2023/7/26 15:48
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
from tools.ZTEax5400Control import ZTEax5400Control

'''
测试步骤
2.4G和5G网络切换

1.DUT connect AP1-2.4G
2.DUT connect AP2-5G
3.Switch wifi between AP1-2.4G and AP2-5G

3.Can Play online video
'''
axus_ssid = 'ATC_ASUS_AX88U_2G'
zte_ssid = 'ZTEax5400_5G'
passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid=axus_ssid, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_5g = Router(band='5 GHz', ssid=zte_ssid, wireless_mode='802.11 a/n/ac', channel='161',
                   bandwidth='20MHz/40MHz/80MHz',
                   authentication_method='WPA-PSK/WPA2-PSK', wpa_passwd='12345678')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    xiaomiControl = ZTEax5400Control()
    ax88uControl.change_setting(router_2g)
    time.sleep(1)
    xiaomiControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    xiaomiControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.forget_network_cmd(target_ip='192.168.2.1')
    pytest.executer.kill_setting()


@pytest.mark.mul_router
def test_check_2g_saved_status():
    pytest.executer.connect_ssid(axus_ssid, passwd)
    pytest.executer.connect_ssid(zte_ssid, passwd, target="192.168.2")
    pytest.executer.enter_wifi_activity()
    pytest.executer.uiautomator_dump()
    assert 'saved' in pytest.executer.get_dump_info() or 'Saved' in pytest.executer.get_dump_info(), "connected ssid not saved"
