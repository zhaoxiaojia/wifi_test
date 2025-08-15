#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/21 09:29
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_change_ap_fail.py
# @Software: PyCharm


import time
from src.test import (Router, connect_ssid, forget_network_cmd, kill_setting,
                      wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.ZTEax5400Control import ZTEax5400Control

'''
测试步骤
连接一个AP1，连接AP2密码错误

1.连接AP1
2.进行AP2连接如果由于AP2的信号非常弱以至于不能连接上，或输入的密码错误导致连接失败

平台会先断开与AP1的连接，尝试着去连接AP2，如果连接失败，则会再次返回自动的连接上AP1
'''


asus_ssid_name = 'ATC_ASUS_AX88U'
zte_ssid_name = 'ZTEax5400_5G'
passwd = 'test1234'
router_ausu = Router(band='2.4G', ssid=asus_ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)
router_zte = Router(band='5G', ssid=zte_ssid_name, wireless_mode='802.11 a/n/ac', channel='161', bandwidth='20MHz/40MHz/80MHz',
                   authentication='WPA-PSK/WPA2-PSK', wpa_passwd=passwd)



@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_ausu)
    ax88uControl.router_control.driver.quit()
    time.sleep(3)
    zte5400Control = ZTEax5400Control()
    zte5400Control.change_setting(router_zte)
    zte5400Control.router_control.driver.quit()
    yield
    forget_network_cmd(target_ip='192.168.50.1')
    forget_network_cmd(target_ip='192.168.2.1')
    kill_setting()


def test_change_ap():
    connect_ssid(asus_ssid_name, passwd)
    kill_setting()
    try:
        connect_ssid(zte_ssid_name,'12345678')
    except AssertionError:
        pytest.dut.back()
        time.sleep(1)
        pytest.dut.back()
    wait_for_wifi_address(target='192.168.50')

