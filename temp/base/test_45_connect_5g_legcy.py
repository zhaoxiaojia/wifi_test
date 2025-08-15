#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_45_connect_5g_legcy.py
# Time       ：2023/7/14 16:01
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试配置
1.设置路由器5G 无线网络名称为“ATC_ASUS_AX88U_5G”，隐藏SSID设置为否，无线模式设置为Legcy，频道带宽设置为20 M,信道设置为149，授权方式为shared key，WEP加密选择 WEP-64bits,无线密码索引选择1，WEP无线密码1设置为Abc1234567
2.连接5G SSID
3.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc1234567'
router_5g = Router(band='5G', ssid=ssid, wireless_mode='Legacy', channel='149', bandwidth='20 MHz',
                   authentication='Shared Key', wep_passwd=passwd, wep_encrypt='WEP-64bits', passwd_index='1')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()


@pytest.mark.wifi_connect
def test_connect_legcy_ssid():
    assert pytest.dut.connect_ssid_via_ui(ssid, passwd), "Can't connect"
