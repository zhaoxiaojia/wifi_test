# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_input_current_passwd.py
# Time       ：2023/8/1 17:06
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
正确密码

1.WIFI列表中选择连接的AP
3.输入正确密码进行连接
3.连接成功后检查wifi状态图标

2.WiFi connect success,tips "Connected successsfully"
3.The corner of wifi icon will show connected.
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
    pytest.executer.connect_ssid(ssid, passwd=passwd)
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"
