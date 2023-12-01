# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_exit_passwd_input.py
# Time       ：2023/8/1 15:39
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
连接一个AP

1.WIFI列表中点击要连接的AP
2.密码键盘输入界面按返回键2次

连接AP时候，密码键盘输入界面按返回键2次退回到WIFI列表界面
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='165', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)

check_info = 'Network & Internet'


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


def test_cancel_input_passwd():
    pytest.executer.find_ssid(ssid)
    pytest.executer.back()
    time.sleep(1)
    pytest.executer.back()
    pytest.executer.uiautomator_dump()
    assert check_info not in pytest.executer.get_dump_info(),"keyboard not be exit"
