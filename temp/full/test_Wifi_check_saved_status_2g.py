# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/22 16:20
# @Author  : Chao.li
# @File    : test_Wifi_check_saved_status_2g.py
# @Project : python
# @Software: PyCharm


import time
from src.test import (Router, connect_save_ssid, connect_ssid, enter_wifi_activity,
                      find_ssid, forget_network_cmd, kill_setting)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Xiaomi.Xiaomiax3600Control import Xiaomiax3600Control

'''
测试步骤
2.4G和5G网络切换

1.DUT connect AP1-2.4G
2.DUT connect AP2-5G
3.Switch wifi between AP1-2.4G and AP2-5G

3.Can Play online video
'''

passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid='ATC_ASUS_AX88U_2G', wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)
router_5g = Router(serial='1', band='5 GHz', ssid='XiaomiAX3000_5G', channel='自动',
                bandwidth='40MHz', authentication='超强加密(WPA3个人版)', wpa_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    xiaomiControl = Xiaomiax3600Control()
    ax88uControl.change_setting(router_2g)
    time.sleep(1)
    xiaomiControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    xiaomiControl.router_control.driver.quit()
    yield
    forget_network_cmd(target_ip='192.168.50.1')
    forget_network_cmd(target_ip='192.168.6.1')
    kill_setting()


def test_check_2g_saved_status():
    connect_ssid('ATC_ASUS_AX88U_2G', passwd)
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"
    connect_ssid('XiaomiAX3000_5G', passwd)
    assert pytest.dut.ping(hostname="192.168.6.1"), "Can't ping"
    enter_wifi_activity()
    pytest.dut.uiautomator_dump()
    assert 'saved' in pytest.dut.get_dump_info(),"connected ssid not saved"


