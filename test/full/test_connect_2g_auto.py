#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_connect_2g_auto.py
# Time       ：2023/7/25 15:15
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
Auto 2.4G

Connect an AP which wireless mode is Auto+2.4G

Platform connect the AP successful
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20/40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_tvsetting()
    pytest.executer.forget_network_cmd()

@pytest.mark.wifi_connect
def test_connect_auto():
    assert pytest.executer.connect_ssid(ssid, passwd=passwd), "Can't connect"
