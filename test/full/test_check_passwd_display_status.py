# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_check_passwd_display_status.py
# Time       ：2023/7/26 15:04
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

连接一个AP，检查当前AP 密码显示

3.“显示密码”选项默认成disable
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='165', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)

check_info = 'resource-id="com.android.tv.settings:id/password_checkbox" class="android.widget.CheckBox" package="com.android.tv.settings" content-desc="" checkable="true" checked="false"'


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()


def test_check_passwd_display_status():
    pytest.executer.find_ssid(ssid)
    pytest.executer.uiautomator_dump()
    assert check_info in pytest.executer.get_dump_info(),'Hide passwd is not disable'
