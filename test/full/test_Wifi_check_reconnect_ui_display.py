# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/24 09:01
# @Author  : Chao.li
# @File    : test_Wifi_check_reconnect_ui_display.py
# @Project : python
# @Software: PyCharm



import logging
import re
import time

import pytest
from test import (Router, connect_save_ssid, connect_ssid, find_ssid,
                        forget_network_cmd, kill_setting,
                        wait_for_wifi_address)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Xiaomi.Xiaomiax3000Control import Xiaomiax3000Control

'''
测试步骤

检查Saved AP2信息

在AP LIST界面再次选择AP2，点击AP2进入"连接操作"提示界面

提示界面会显示AP2的SSID和信号强度，同时有“连接/不保存/取消”3个选项
'''

asus_ssid_name = 'ATC_ASUS_AX88U'
xiaomi_ssid_name = 'XiaomiAX3000_5G'
passwd = 'test1234'
router_ausu = Router(band='2.4 GHz', ssid=asus_ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_xiaomi = Router(serial='1', band='5 GHz', ssid=xiaomi_ssid_name, channel='自动',
                       bandwidth='40MHz', authentication_method='超强加密(WPA3个人版)', wpa_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_ausu)
    time.sleep(1)
    xiaomiControl = Xiaomiax3000Control()
    xiaomiControl.change_setting(router_xiaomi)
    ax88uControl.router_control.driver.quit()
    xiaomiControl.router_control.driver.quit()
    yield
    forget_network_cmd(target_ip='192.168.50.1')
    forget_network_cmd(target_ip='192.168.6.1')
    kill_setting()


def test_repeat_change_ap():
    connect_ssid(asus_ssid_name, passwd, target='192.168.50')
    kill_setting()
    connect_ssid(xiaomi_ssid_name, passwd, target='192.168.6')
    kill_setting()
    find_ssid(asus_ssid_name)
    pytest.dut.uiautomator_dump()
    assert 'Connect' in pytest.dut.get_dump_info(),"Display not currently"
    assert 'Forget network' in pytest.dut.get_dump_info(),"Display not currently"