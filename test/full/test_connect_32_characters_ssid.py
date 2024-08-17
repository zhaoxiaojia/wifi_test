# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_32_characters_ssid.py
# Time       ：2023/7/31 15:00
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
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
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.kill_setting()


@pytest.mark.wifi_connect
def test_connect_ssid_with_char_and_number():
    assert pytest.executer.connect_ssid(ssid, passwd), "Can't connect"
