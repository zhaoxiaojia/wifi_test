# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_2g_hide_open.py
# Time       ：2023/8/1 15:54
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
1.配置一个不加密关闭SSID广播的AP
2.DUT添加一个网络，编辑网络时SSID及加密与配置的测试AP一致
3.WiFi扫描（网络中需要没有其他连接成功过的AP）

channel 1

可以自动连接测试AP成功
'''

ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20 MHz',
                   authentication_method='Open System', hide_ssid='是')


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
def test_connect_conceal_ssid():
    pytest.executer.add_network(ssid, 'None')
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"
