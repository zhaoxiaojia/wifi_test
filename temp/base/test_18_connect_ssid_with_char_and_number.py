#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_18_connect_ssid_with_char_and_number.py
# Time       ：2023/7/13 17:18
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试步骤
1.设置2.4G AP SSID 为32个字符或数字
2.WIFI列表界面扫描该AP
3.DUT连接该AP
'''

ssid = '12345678901234567890123456789012'
passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)


@pytest.mark.wifi_connect
@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()


def test_connect_ssid_with_char_and_number():
    pytest.dut.connect_ssid_via_ui(ssid, passwd)
    assert pytest.dut.wait_for_wifi_address(), "Connect fail"
