# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_check_ssid.py
# Time       ：2023/7/31 14:30
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging
import os
import time

import pytest

from tools.Asusax88uControl import Asusax88uControl
from Router import Router
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
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.kill_tvsetting()


def test_check_ssid():
    assert pytest.executer.connect_ssid(ssid), "Can't connect"
    assert pytest.executer.ping(hostname="192.168.50.1"), "Can't ping"
    pytest.executer.enter_wifi_activity()
    pytest.executer.wait_element('Available networks','text')
    pytest.executer.tap(1469,410)
    pytest.executer.wait_element('Internet connection','text')
    pytest.executer.uiautomator_dump()
    assert ssid in pytest.executer.get_dump_info(),'SSID not current'
