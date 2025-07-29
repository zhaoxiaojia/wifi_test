# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/19 13:48
# @Author  : Chao.li
# @File    : test_Wifi_input_current_passwd.py
# @Project : python
# @Software: PyCharm


from src.test import (Router, connect_ssid, forget_network_cmd, kill_setting,
                      wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
正确密码

1.WIFI列表中选择连接的AP
3.输入正确密码进行连接
3.连接成功后检查wifi状态图标

2.WiFi connect success,tips "Connected successsfully"
3.The corner of wifi icon will show connected.
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20/40 MHz',
                   authentication_method='WPA/WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_connect_auto():
    connect_ssid(ssid, passwd=passwd)
    assert wait_for_wifi_address(), "Connect fail"
