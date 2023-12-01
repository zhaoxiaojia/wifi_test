#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_18_connect_ssid_with_char_and_number.py
# Time       ：2023/7/13 17:18
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
1.设置2.4G AP SSID 为32个字符或数字
2.WIFI列表界面扫描该AP
3.DUT连接该AP
'''

ssid = '12345678901234567890123456789012'
passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.mark.wifi_connect
@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.kill_setting()


def test_connect_ssid_with_char_and_number():
    pytest.executer.connect_ssid(ssid, passwd)
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"
