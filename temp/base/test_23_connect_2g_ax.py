#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_23_connect_2g_ax.py
# Time       ：2023/7/14 11:03
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试步骤
1.设置路由器2.4G 无线网络名称为“ATC_ASUS_AX88U_2G”，隐藏SSID设置为否，无线模式设置为AX only，频道带宽设置为20/40M,信道设置为自动，授权方式为open
2.连接2.4G SSID
3.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''
ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4G', ssid=ssid, wireless_mode='AX only', channel='自动', bandwidth='20/40 MHz',
                   authentication='Open System')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()

@pytest.mark.wifi_connect
def test_connect_ssid_wireless_ax():
    pytest.dut.connect_ssid_via_ui(ssid)
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"
