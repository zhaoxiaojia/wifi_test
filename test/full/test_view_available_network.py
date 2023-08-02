# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_view_available_network.py
# Time       ：2023/8/2 10:53
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import os
import time

import pytest

from tools.Asusax88uControl import Asusax88uControl
from Router import Router
'''
测试配置
View available network

1.连接AP输入错误的密码
2.连接失败后选择View available network

2.WiFi connect fail，and try 3 times -> then toast“WiFi password not valid”,Pop [Try again]/View available networkd;
3.If select [View available networkd] dut will goto wifi list , the AP1 will show [Check password and try again]
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20/40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)



@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_tvsetting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')

@pytest.mark.wifi_connect
def test_wrong_passwd():
    pytest.executer.find_ssid(ssid)
    pytest.executer.text('wrongpasswd')
    pytest.executer.keyevent(66)
    for _ in range(3):
        pytest.executer.wait_and_tap('Try again','text',times=10)
        time.sleep(1)
        pytest.executer.keyevent(66)
        pytest.executer.keyevent(66)
        pytest.executer.wait_element('Wi-Fi password not valid','text')
    pytest.executer.wait_and_tap('View available networks','text')
    assert not pytest.executer.ping('192.168.50.1'),'should be no ip address'
    time.sleep(2)
    pytest.executer.uiautomator_dump()
    assert 'Check password and try again' in pytest.executer.get_dump_info(),'Display error'
