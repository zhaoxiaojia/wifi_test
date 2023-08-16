#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_22_connect_2g_auto.py
# Time       ：2023/7/14 10:59
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
1.设置路由器2.4G 无线网络名称为“ATC_ASUS_AX88U_2G”，隐藏SSID设置为否，无线模式设置为Auto，频道带宽设置为20/40M,信道设置为自动，授权方式为open
2.连接2.4G SSID
3.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''

ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='自动', bandwidth='20/40 MHz',
                   authentication_method='Open System')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd()
    pytest.executer.kill_tvsetting()

@pytest.mark.wifi_connect
def test_connect_ssid_wireless_auto():
    pytest.executer.connect_ssid(ssid)
    assert pytest.executer.ping(hostname="192.168.50.1"), "Can't ping"