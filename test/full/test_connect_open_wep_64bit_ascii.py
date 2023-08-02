# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_open_wep_64bit_ascii.py
# Time       ：2023/7/31 16:13
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import os
import time

import pytest

from tools.Asusax88uControl import Asusax88uControl
from Router import Router

'''
测试配置
OPNE WEP 64bit ASCII

Connect an AP which authentication method is WEP &Certification Type:Open System & 64bit &ASCII

Platform connect the AP successful
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='Legacy', channel='1', bandwidth='20 MHz',
                   authentication_method='Open System', wep_passwd=passwd, wep_encrypt='WEP-64bits')


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_tvsetting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


@pytest.mark.wifi_connect
def test_connect_wep64():
    assert pytest.executer.connect_ssid(ssid, passwd), "Can't connect"
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"
