#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_42_connect_5g_auto.py
# Time       ：2023/7/14 15:50
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.设置路由器5G 无线网络名称为“ATC_ASUS_AX88U_5G”，隐藏SSID设置为否，无线模式设置为Auto，频道带宽设置为20/40/80M,信道设置为149，授权方式为open
2.连接5G SSID
3.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''

ssid = 'ATC_ASUS_AX88U_5G'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='149', bandwidth='20/40/80 MHz',
                   authentication_method='Open System')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.kill_setting()


@pytest.mark.wifi_connect
def test_connect_ssid_wireless_auto():
    pytest.executer.connect_ssid(ssid), "Can't connect"
    assert pytest.executer.ping(hostname="192.168.50.1"), "Can't ping"
