# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_check_hide_passwd_display.py
# Time       ：2023/7/26 15:01
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


import logging
import re
import time

import pytest

from Router import Router
from tools.Asusax88uControl import Asusax88uControl

'''
测试步骤
连接一个AP

1.WIFI列表中点击要连接的AP
2.输入密码时选择”隐藏密码“

连接AP时候，密码键盘输入界面，输入密码时，如果“隐藏密码”是设置成enable，则密码全部以“……”的保密形式显示
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
    pytest.executer.checkoutput('input text 12345678')
    pytest.executer.keyevent(4)
    time.sleep(1)
    pytest.executer.keyevent(20)
    time.sleep(1)
    pytest.executer.keyevent(23)
    pytest.executer.uiautomator_dump()
    assert 'text="••••••••"' in pytest.executer.get_dump_info(), 'Passwd not be hidden'
