# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/15 16:22
# @Author  : Chao.li
# @Site    :
# @File    : test_Wifi_connect_default.py
# @Project : python
# @Software: PyCharm



import logging
import re
import time

import pytest
from test import (Router, connect_ssid, forget_network_cmd,
                        kill_setting)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
连接加密方式为默认的AP

Connect an AP which authentication method is Default(Auto)

Platform connect the AP successful
'''


ssid_name = 'ATC_ASUS_AX88U_2G'
passwd = '0123456789'
router_2g = Router(band='2.4 GHz', ssid=ssid_name, wireless_mode='Legacy', channel='自动', bandwidth='20 MHz',
                   authentication_method='Shared Key', wep_passwd=passwd,wep_encrypt='WEP-64bits')



@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    forget_network_cmd(target_ip='192.168.50.1')
    kill_setting()


def test_connect_default():
    assert connect_ssid(ssid_name, passwd), "Can't connect"
    assert pytest.executer.ping(hostname="192.168.50.1"), "Can't ping"