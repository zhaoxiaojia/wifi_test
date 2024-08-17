# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_hide_wpa2_incorrect_type.py
# Time       ：2023/8/1 16:57
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
1.配置一个WPA2密码加密 关闭SSID广播的AP
2.DUT新建一个连接 SSID与测试AP一致，加密方式不一致
3.WiFi扫描（网络中需要没有其他连接成功过的AP）

channel 1

不会连接成功，也不会提示连接失败
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20/40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd, hide_ssid='是')



@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd()

@pytest.mark.wifi_connect
def test_connect_wpa2_wrong_type():
    try:
        pytest.executer.add_network(ssid, 'WEP', passwd=passwd)
        result = False
    except AssertionError as e:
        result = True
    assert result,"Should not connected"
