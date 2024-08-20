# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/18 10:40
# @Author  : Chao.li
# @File    : test_Wifi_check_ssid.py
# @Project : python
# @Software: PyCharm


import logging
import os
import time

import pytest
from test import (Router, connect_ssid, enter_wifi_activity,
                        forget_network_cmd, kill_setting)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
连接一个AP

连接一个AP，检查当前AP SSID

1.显示当前AP的SSID
'''

ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='自动', bandwidth='20/40 MHz',
                   authentication_method='Open System')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    # forget_network_cmd(target_ip='192.168.50.1',ssid=ssid)
    # kill_setting()


def test_check_ssid():
    assert connect_ssid(ssid), "Can't connect"
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"
    enter_wifi_activity()
    pytest.dut.wait_element('Available networks','text')
    pytest.dut.tap(1469,410)
    pytest.dut.wait_element('Interet connection','text')
    pytest.dut.uiautomator_dump()
    assert ssid in pytest.dut.get_dump_info(),'SSID not current'
