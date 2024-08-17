# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_change_ap_fail.py
# Time       ：2023/7/26 10:46
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import time

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.ZTEax5400Control import ZTEax5400Control

'''
测试步骤
连接一个AP1,连接AP2密码错误

1.连接AP1
2.进行AP2连接如果由于AP2的信号非常弱以至于不能连接上，或输入的密码错误导致连接失败

平台会先断开与AP1的连接,尝试着去连接AP2,如果连接失败,则会再次返回自动的连接上AP1
'''

asus_ssid_name = 'ATC_ASUS_AX88U'
zte_ssid_name = 'ZTEax5400_5G'
passwd = 'test1234'
router_ausu = Router(band='2.4 GHz', ssid=asus_ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_zte = Router(band='5 GHz', ssid=zte_ssid_name, wireless_mode='802.11 a/n/ac', channel='161',
                    bandwidth='20MHz/40MHz/80MHz',
                    authentication_method='WPA-PSK/WPA2-PSK', wpa_passwd=passwd)


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
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.kill_setting()

@pytest.mark.mul_router
def test_change_ap():
    pytest.executer.connect_ssid(asus_ssid_name, passwd)
    pytest.executer.kill_setting()
    try:
        pytest.executer.connect_ssid(zte_ssid_name, "12345678")
    except AssertionError:
        pytest.executer.back()
        time.sleep(1)
        pytest.executer.back()
    pytest.executer.wait_for_wifi_address()
