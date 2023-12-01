# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_input_wrong_passwd_try_again.py
# Time       ：2023/8/2 9:11
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import os
import time

import pytest

from Router import Router
from tools.Asusax88uControl import Asusax88uControl

'''
测试配置
Try again

1.连接AP输入错误的密码
2.连接失败后选择Try again

2.WiFi connect fail,and try 3 times -> then toast“WiFi password not valid”,Pop [Try again]/View available networkd;
3.If select [Try again] dut will try connect
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
    pytest.executer.kill_setting()
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
