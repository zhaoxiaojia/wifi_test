# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_default.py
# Time       ：2023/7/31 16:06
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""




import logging
import re
import time

import pytest

from tools.Asusax88uControl import Asusax88uControl
from Router import Router
'''
测试步骤
连接加密方式为默认的AP

Connect an AP which authentication method is Default(Auto)

Platform connect the AP successful
'''


ssid_name = 'ATC_ASUS_AX88U_2G'
passwd = '0123456789'
router_2g = Router(band='2.4 GHz', ssid=ssid_name, wireless_mode='Legacy', channel='自动', bandwidth='20 MHz',authentication_method='Shared Key', wep_passwd=passwd,wep_encrypt='WEP-64bits')



@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd()
    pytest.executer.kill_tvsetting()

@pytest.mark.wifi_connect
def test_connect_default():
    assert pytest.executer.connect_ssid(ssid_name, passwd), "Can't connect"
    assert pytest.executer.ping(hostname="192.168.50.1"), "Can't ping"