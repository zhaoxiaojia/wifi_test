# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_single_ssid.py
# Time       ：2023/8/1 14:40
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
set single ssid

1.AP 5G和2.4G设置相同的SSID和密码类型以及密码；
2.DUT连接AP（强信号）

默认连接5G
'''


ssid_name = 'ATC_ASUS_AX88U'
passwd = 'test1234'
router_2g = Router(band='2.4 GHz', ssid=ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_5g = Router(band='5 GHz', ssid=ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    # ax88uControl.router_control.driver.quit()
    time.sleep(1)
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.kill_setting()

@pytest.mark.wifi_connect
def test_connect_ssid_wireless_auto():
    assert pytest.executer.connect_ssid(ssid_name, passwd), "Can't connect"
    assert pytest.executer.ping(hostname="192.168.50.1"), "Can't ping"
    assert 'freq: 5' in pytest.executer.checkoutput(pytest.executer.IW_LINNK_COMMAND), "Doesn't conect 5g "
