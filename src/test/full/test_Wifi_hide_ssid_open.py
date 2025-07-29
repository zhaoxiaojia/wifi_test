#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/4 11:19
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_hide_ssid_open.py
# @Software: PyCharm


from src.test import (Router, add_network, forget_network_cmd, kill_setting,
                      wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
1.配置一个不加密 关闭SSID广播的AP
2.DUT添加一个网络，编辑网络时SSID及加密与配置的测试AP一致
3.WiFi扫描（网络中需要没有其他连接成功过的AP）

channel 157

可以自动连接测试AP成功
'''

ssid = 'ATC_ASUS_AX88U_5G'
router_2g = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='157', bandwidth='80 MHz',
                   authentication_method='Open System', hide_ssid='是')


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_connect_conceal_ssid():
    add_network(ssid, 'None')
    assert wait_for_wifi_address(), "Connect fail"
