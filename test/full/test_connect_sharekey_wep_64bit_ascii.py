# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_sharekey_wep_64bit_ascii.py
# Time       ：2023/8/1 14:20
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


import logging
import os
import time

import pytest

from Router import Router
from tools.Asusax88uControl import Asusax88uControl

'''
测试配置
ShareKey WEP 64bit ASCII

Connect an AP which authentication method is WEP &Certification Type:ShareKey  & 64bit &ASCII

Platform connect the AP successful
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='Legacy', channel='1', bandwidth='20 MHz',
                   authentication_method='Shared Key', wep_passwd=passwd,wep_encrypt='WEP-64bits')



@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')

@pytest.mark.wifi_connect
def test_connect_wep64():
    pytest.executer.connect_ssid(ssid, passwd)
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"

