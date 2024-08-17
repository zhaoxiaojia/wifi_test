# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_check_passwd_hide_button.py
# Time       ：2023/7/26 15:11
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
连接一个AP

连接一个AP，检查当前AP 密码显示

3.“显示密码”选项默认成disable
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd= '12345678'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='自动', bandwidth='20/40 MHz',
                   authentication_method='WPA2-Personal',wpa_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()

def test_check_passwd_hide_button():
    pytest.executer.find_ssid(ssid)
    pytest.executer.text(passwd)
    pytest.executer.uiautomator_dump()
    assert passwd in pytest.executer.get_dump_info(),'passwd not shown'