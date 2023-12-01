# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_32_chars_ssid.py
# Time       ：2023/7/26 10:33
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

'''
测试步骤
SSID最大长度检查

4.验证32个字符的SSID是否能显示完整

32个字符的SSID能显示完整
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
    pytest.executer.forget_network_cmd()
    pytest.executer.kill_setting()


@pytest.mark.wifi_connect
def test_connect_ssid_with_char_and_number():
    assert pytest.executer.connect_ssid(ssid, passwd=passwd), "Can't connect"
