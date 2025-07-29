#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/25 10:33
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_5g_axonly.py
# @Software: PyCharm


from src.test import (Router, connect_ssid, forget_network_cmd, kill_setting,
                      wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
802.11 AX 5G

Connect an AP which wireless mode is 802.11 AX-5G

Platform connect the AP successful
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='AX only', channel='44', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_axonly():
    connect_ssid(ssid, passwd=passwd)
    assert wait_for_wifi_address(), "Connect fail"
