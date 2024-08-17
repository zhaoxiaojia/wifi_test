# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_hide_open_incorrect_type.py
# Time       ：2023/8/1 15:48
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
1.配置一个不加密 关闭SSID广播的AP
2.DUT新建一个连接 SSID与测试AP一致，加密方式不一致
3.WiFi扫描（网络中需要没有其他连接成功过的AP

channel 157

不会连接成功，也不会提示连接失败
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='157', bandwidth='20/40/80 MHz',
                   authentication_method='Open System', hide_ssid='是')



@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')

@pytest.mark.wifi_connect
def test_connect_open_wrong_type():
    try:
        pytest.executer.add_network(ssid, 'WPA/WPA2-Personal', passwd=passwd)
        result = False
    except AssertionError as e:
        result = True
    assert result,"Should not connected"
