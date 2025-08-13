#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_12_reconnect_forgetted.py
# Time       ：2023/7/13 16:30
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import time

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试步骤
1.连接任一AP；
2.进入WiFi列表，忘记已连接的AP
3.再次连接已忘记的AP
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()

    yield
    pytest.dut.kill_setting()
    pytest.dut.forget_network_cmd(target_ip="192.168.50.1")


def test_reconnect_forgetted_ssid():
    pytest.dut.connect_ssid_via_ui(ssid, passwd)
    pytest.dut.kill_setting()
    pytest.dut.find_ssid(ssid)
    pytest.dut.wait_and_tap('Forget network', 'text')
    for _ in range(5):
        if pytest.dut.find_element('Internet connection', 'text'):
            break
        time.sleep(1)
        pytest.dut.keyevent(23)
        pytest.dut.keyevent(23)
    pytest.dut.uiautomator_dump()
    while 'Not connected' not in pytest.dut.get_dump_info():
        time.sleep(1)
        pytest.dut.uiautomator_dump()
    pytest.dut.kill_setting()
    assert pytest.dut.connect_ssid_via_ui('ATC_ASUS_AX88U_2G', '12345678'), "Connect fail"
