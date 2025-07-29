# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/19 10:21
# @Author  : Chao.li
# @File    : test_Wifi_view_available_network.py
# @Project : python
# @Software: PyCharm


import time
from src.test import (Router, find_ssid, forget_network_cmd, kill_setting,
                      wait_for_wifi_address, wait_keyboard)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

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
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_wrong_passwd():
    find_ssid(ssid)
    pytest.dut.text('wrongpasswd')
    pytest.dut.keyevent(66)
    for _ in range(3):
        pytest.dut.wait_and_tap('Try again','text',times=10)
        time.sleep(1)
        pytest.dut.keyevent(66)
        pytest.dut.keyevent(66)
        pytest.dut.wait_element('Wi-Fi password not valid','text')
    pytest.dut.wait_and_tap('View available networks','text')
    assert not pytest.dut.ping('192.168.50.1'),'should be no ip address'
    pytest.dut.uiautomator_dump()
    assert 'Check password and try again' in pytest.dut.get_dump_info(),'Display error'
