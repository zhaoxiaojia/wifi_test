# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_multi_ssid.py
# Time       ：2023/7/31 16:10
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


import logging
import time

import pytest

from Router import Router
from tools.Asusax88uControl import Asusax88uControl

'''
测试步骤
SSID is set to 10 character or number，then platform connect the AP

Platform connect the AP successful
'''


ssid_name = '0123456789'
passwd = 'test1234'
router_2g = Router(band='2.4 GHz', ssid=ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)



@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    # ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.kill_setting()

@pytest.mark.wifi_connect
def test_connect_multi_ssid():
    assert pytest.executer.connect_ssid(ssid_name, passwd), "Can't connect"
    assert pytest.executer.ping(hostname="192.168.50.1"), "Can't ping"
