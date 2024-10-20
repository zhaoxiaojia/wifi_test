#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/26 14:27
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_channel_1.py
# @Software: PyCharm




import logging
import os
import time
from test import (Router, connect_ssid, forget_network_cmd, kill_setting,
                  wait_for_wifi_address)

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
Auto mode 信道1

Connect an AP which channel is 1

Platform connect the AP successful
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20/40 MHz',
                   authentication_method='WPA/WPA2-Personal', wpa_passwd=passwd)



@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_channel_1():
    connect_ssid(ssid, passwd=passwd)
    assert wait_for_wifi_address(), "Connect fail"
