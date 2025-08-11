# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/23 16:07
# @Author  : Chao.li
# @File    : test_Wifi_reconnect_saved_ssid.py
# @Project : python
# @Software: PyCharm


import time
from src.test import (Router, connect_save_ssid, connect_ssid, find_ssid,
                      forget_network_cmd, kill_setting, wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Xiaomi.Xiaomiax3600Control import Xiaomiax3600Control

'''
测试步骤

连接网络

选择“连接”选项

自动连接上AP2
'''

asus_ssid_name = 'ATC_ASUS_AX88U'
xiaomi_ssid_name = 'XiaomiAX3000_5G'
passwd = 'test1234'
router_ausu = Router(band='2.4 GHz', ssid=asus_ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                     authentication='WPA2-Personal', wpa_passwd=passwd)
router_xiaomi = Router(serial='1', band='5 GHz', ssid=xiaomi_ssid_name, channel='自动',
                       bandwidth='40MHz', authentication='超强加密(WPA3个人版)', wpa_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_ausu)
    time.sleep(1)
    xiaomiControl = Xiaomiax3600Control()
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
    connect_save_ssid(asus_ssid_name)
