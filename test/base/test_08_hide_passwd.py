#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_08_hide_passwd.py
# Time       ：2023/7/13 10:26
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import time

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.进入设置-WiFi列表界面
2.选择任一AP，输入密码界面，勾选"Hide password"，输入正确密码，连接AP
'''

router = Router(band='5 GHz', ssid='ATC_ASUS_AX88U_5G', wireless_mode='N/AC/AX mixed', channel='36', bandwidth='40 MHz',
                authentication_method='WPA2-Personal', wpa_passwd='12345678')

TARGET_IP = "192.168.50.1"


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()


def test_hide_passwd():
    pytest.executer.find_ssid('ATC_ASUS_AX88U_5G')
    pytest.executer.wait_keyboard()
    pytest.executer.text('12345678')
    pytest.executer.keyevent(4)
    time.sleep(1)
    pytest.executer.keyevent(20)
    time.sleep(1)
    pytest.executer.keyevent(23)
    pytest.executer.uiautomator_dump()
    assert 'text="••••••••"' in pytest.executer.get_dump_info(), 'Passwd not be hidden'
