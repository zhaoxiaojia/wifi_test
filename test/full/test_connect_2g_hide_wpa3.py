#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_connect_2g_hide_wpa3.py
# Time       ：2023/7/25 15:36
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
1.配置一个WPA3密码加密关闭SSID广播的AP
2.DUT新建一个连接SSID与加密与测试AP一致
3.WiFi扫描（网络中需要没有其他连接成功过的AP）

工作信道设置在1信道

可以自动连接测试AP成功
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20/40 MHz',
                   authentication_method='WPA3-Personal', wpa_passwd=passwd, hide_ssid='是')



@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')

@pytest.mark.wifi_connect
def test_connect_wpa3():
    assert pytest.executer.add_network(ssid, 'WPA3-Personal', passwd=passwd),"Can't connect to WPA3-Personal"
