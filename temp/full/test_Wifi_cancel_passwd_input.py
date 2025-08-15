#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/18 10:48
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_cancel_passwd_input.py
# @Software: PyCharm


from src.test import (Router, find_ssid, forget_network_cmd, kill_setting,
                      wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
连接一个AP

1.WIFI列表中点击要连接的AP
2.密码键盘输入界面按返回键

连接AP时候，密码键盘输入界面按返回键密码键盘退出
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5G', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='165', bandwidth='40 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)

check_info = 'com.google.android.inputmethod.latin'


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_cancel_input_passwd():
    find_ssid(ssid)
    pytest.dut.back()
    pytest.dut.uiautomator_dump()
    assert check_info not in pytest.dut.get_dump_info(),"keyboard not be exit"
