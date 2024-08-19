#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/24 09:52
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_32_characters_ssid.py
# @Software: PyCharm



import logging
import re
import time

import pytest
from test import (Router, enter_wifi_activity, find_ssid,
                        forget_network_cmd, kill_setting,
                        wait_for_wifi_address)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
SSID最大长度检查

4.验证32个字符的SSID是否能显示完整；

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
    forget_network_cmd(target_ip='192.168.50.1')
    kill_setting()

@pytest.mark.flaky(reruns=3)
def test_connect_ssid_with_char_and_number():
    assert find_ssid(ssid),"Can't display currently"
