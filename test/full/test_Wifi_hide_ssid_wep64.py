#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/4 13:52
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_hide_ssid_wep64.py
# @Software: PyCharm


import logging
import os
import time

import pytest
from test import (Router, add_network, forget_network_cmd,
                        kill_setting, wait_for_wifi_address)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
1.配置一个WEP-64bits加密关闭SSID广播的AP
2.DUT新建一个连接SSID与加密与测试AP一致
3.WiFi扫描（网络中需要没有其他连接成功过的AP

channel 157

可以自动连接测试AP成功
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc1234567'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='Legacy', channel='157', bandwidth='20 MHz',
                   authentication_method='Shared Key', wep_passwd=passwd, wep_encrypt='WEP-64bits', passwd_index='1',hide_ssid='是')


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_connect_wep64():
    add_network(ssid, 'WEP', passwd=passwd)
    assert wait_for_wifi_address(), "Connect fail"