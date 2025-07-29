#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/18 10:17
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_check_hide_passwd_display.py
# @Software: PyCharm


import time
from src.test import Router, enter_wifi_activity, find_ssid, kill_setting

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

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
    find_ssid('ATC_ASUS_AX88U_5G')
    yield
    kill_setting()


def test_hide_passwd():
    pytest.dut.checkoutput('input text 12345678')
    pytest.dut.keyevent(4)
    time.sleep(1)
    pytest.dut.keyevent(20)
    time.sleep(1)
    pytest.dut.keyevent(23)
    pytest.dut.uiautomator_dump()
    assert 'text="••••••••"' in pytest.dut.get_dump_info(), 'Passwd not be hidden'
