#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/18 10:05
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_check_passwd_display_status.py
# @Software: PyCharm


import logging
import os
import time

import pytest
from test import (Router, find_ssid, forget_network_cmd, kill_setting,
                        wait_for_wifi_address)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

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
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_check_passwd_display_status():
    find_ssid(ssid)
    pytest.executer.uiautomator_dump()
    assert check_info in pytest.executer.get_dump_info(),'Hide passwd is not disable'
