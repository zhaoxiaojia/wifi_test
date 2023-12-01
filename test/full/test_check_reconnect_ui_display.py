# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_check_reconnect_ui_display.py
# Time       ：2023/7/26 15:14
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
from tools.ZTEax5400Control import ZTEax5400Control

'''
测试步骤

检查Saved AP2信息

在AP LIST界面再次选择AP2，点击AP2进入"连接操作"提示界面

提示界面会显示AP2的SSID和信号强度，同时有“连接/不保存/取消”3个选项
'''

asus_ssid_name = 'ATC_ASUS_AX88U'
zte_ssid_name = 'ZTEax5400_5G'
passwd = 'test1234'
router_ausu = Router(band='2.4 GHz', ssid=asus_ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_zte = Router(band='5 GHz', ssid=zte_ssid_name, wireless_mode='802.11 a/n/ac', channel='161',
                    bandwidth='20MHz/40MHz/80MHz',
                    authentication_method='WPA-PSK/WPA2-PSK', wpa_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_ausu)
    time.sleep(1)
    zteControl = ZTEax5400Control()
    zteControl.change_setting(router_zte)
    ax88uControl.router_control.driver.quit()
    zteControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.forget_network_cmd(target_ip='192.168.2.1')
    pytest.executer.kill_setting()


@pytest.mark.wifi_connect
@pytest.mark.mul_router
def test_repeat_change_ap():
    pytest.executer.connect_ssid(asus_ssid_name, passwd, target="192.168.50")
    pytest.executer.kill_setting()
    pytest.executer.connect_ssid(zte_ssid_name, passwd, target="192.168.2")
    pytest.executer.kill_setting()
    pytest.executer.find_ssid(asus_ssid_name)
    pytest.executer.uiautomator_dump()
    assert 'Connect' in pytest.executer.get_dump_info(), "Display not currently"
    assert 'Forget network' in pytest.executer.get_dump_info(), "Display not currently"
