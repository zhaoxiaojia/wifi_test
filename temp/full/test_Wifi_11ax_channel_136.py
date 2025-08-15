#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/5/6 13:50
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_11ax_channel_136.py
# @Software: PyCharm


from src.test import (Router, connect_ssid, forget_network_cmd, kill_setting,
                      wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
11ax mode 信道136

Connect an AP which channel is 5G AX-136

Platform connect the AP successful
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5G', ssid=ssid, wireless_mode='AX only', channel='136', bandwidth='40 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_channel_136():
    connect_ssid(ssid, passwd=passwd)
    assert wait_for_wifi_address(), "Connect fail"
