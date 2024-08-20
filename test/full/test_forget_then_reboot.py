# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/25 10:35
# @Author  : Chao.li
# @File    : test_forget_then_reboot.py
# @Project : python
# @Software: PyCharm



import logging
import os
import time

import pytest
from test import (Router, connect_ssid, forget_network_cmd,
                        kill_setting, wait_for_wifi_address,
                        wait_for_wifi_service)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
忘记网络重启

1.Enter wifi list ，forget the current AP1  network
2.Reboot DUT.

DUT will not auto  reconnect  AP1 wifi
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='AX only', channel='36', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_forget_then_reboot():
    connect_ssid(ssid, passwd=passwd)
    assert wait_for_wifi_address(), "Connect fail"
    forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.reboot()
    wait_for_wifi_service()
    try:
        wait_for_wifi_address()
        assert False,"Should not reconnect"
    except AssertionError:
        assert True
