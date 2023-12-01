# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_2g_channel_11.py
# Time       ：2023/7/26 14:47
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
Auto mode 信道11

Connect an AP which channel is 11
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='11', bandwidth='20/40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


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
def test_channel_11():
    assert pytest.executer.connect_ssid(ssid, passwd=passwd), "Can't connect"
