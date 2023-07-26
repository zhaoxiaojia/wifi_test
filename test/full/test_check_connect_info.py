# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_check_connect_info.py
# Time       ：2023/7/26 14:58
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


import logging
import os
import time
import re
import pytest
from tools.Asusax88uControl import Asusax88uControl
from Router import Router
'''
测试配置
连接一个AP

1.WIFI列表中连接目标AP
2.检查连接上的AP在AP LIST中的位置和状态

此时在AP LIST界面，当前连接的AP会自动排列在第一位，help text显示“已连接”。
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='165', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)

check_info = 'ATC_ASUS_AX88U_5G,Connected'


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_tvsetting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


def test_check_connect_info():
    pytest.executer.connect_ssid(ssid,passwd)
    pytest.executer.wait_element('NetWork & Internet','text')
    pytest.executer.uiautomator_dump()
    assert check_info in pytest.executer.get_dump_info(),'help text display wrong info'