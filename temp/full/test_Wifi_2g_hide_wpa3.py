#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/11 16:48
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_2g_hide_wpa3.py
# @Software: PyCharm


from src.test import (Router, add_network, forget_network_cmd, kill_setting,
                      wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

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
router_2g = Router(band='2.4G', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20/40 MHz',
                   authentication='WPA3-Personal', wpa_passwd=passwd, hide_ssid='是')



@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_connect_wpa3():
    add_network(ssid, 'WPA3-Personal', passwd=passwd)
    assert wait_for_wifi_address(), "Connect fail"
