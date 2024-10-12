#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/24 10:04
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_connect_32_characters_ssid.py
# @Software: PyCharm



import logging
import re
import time
from test import (Router, connect_ssid, enter_wifi_activity,
                  forget_network_cmd, kill_setting, wait_for_wifi_address)

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
32个字符或数字的SSID

SSID is set to 32 character or number，then platform connect the AP

Platform connect the AP successful
'''

ssid = '12345678901234567890123456789012'
passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    forget_network_cmd(target_ip='192.168.50.1')
    kill_setting()

@pytest.mark.flaky(reruns=3)
def test_connect_ssid_with_char_and_number():
    connect_ssid(ssid, passwd)
    assert wait_for_wifi_address(), "Connect fail"
