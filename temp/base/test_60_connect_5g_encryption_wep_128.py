#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_60_connect_5g_encryption_wep_128.py
# Time       ：2023/7/14 17:52
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试步骤
1.设置路由器5G 无线网络名称为“ATC_ASUS_AX88U_5G”，隐藏SSID设置为否，无线模式设置为Legcy，频道带宽设置为20/40/80M,信道设置为149,授权方式为shared key,WEP加密选择WPE-128bit，WEP无线密码设置为1234567890123，受保护的管理帧设置为强制启用
2.连接5G SSID
3.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''
ssid = 'ATC_ASUS_AX88U_5G'
passwd = '1234567890123'
router_5g = Router(band='5G', ssid=ssid, wireless_mode='Legacy', channel='149', bandwidth='20 MHz',
                   authentication='Shared Key', wep_encrypt='WEP-128bits', wep_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()


@pytest.mark.wifi_connect
def test_connect_ssid_encryption_wep_128():
    pytest.dut.connect_ssid_via_ui(ssid, passwd)
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"
