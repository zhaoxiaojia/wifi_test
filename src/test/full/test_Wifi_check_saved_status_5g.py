# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/22 16:55
# @Author  : Chao.li
# @File    : test_Wifi_check_saved_status_5g.py
# @Project : python
# @Software: PyCharm


import time
from src.test import (Router, connect_save_ssid, connect_ssid, enter_wifi_activity,
                      find_ssid, forget_network_cmd, kill_setting)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Xiaomi.Xiaomiax3000Control import Xiaomiax3000Control

'''
测试步骤
5GSaved的网络检查

1.Dut connect AP1-5G；
2.Dut connect AP2-5G
3.Dut connect AP!-5G

3.When reconnect AP1-5G ->Exist [Connect]\[Forget network]->If select  connect ap, dut will reconnect successfully, if Select forget, will get, dut will forget the network
'''

passwd = '12345678'
router_5g = Router(band='5 GHz', ssid='ATC_ASUS_AX88U_5G', wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)
router_2g = Router(serial='1', band='2.4 GHz', ssid='XiaomiAX3000_2G', channel='自动',
                bandwidth='40MHz', authentication='超强加密(WPA3个人版)', wpa_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    xiaomiControl = Xiaomiax3000Control()
    ax88uControl.change_setting(router_5g)
    time.sleep(1)
    xiaomiControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    xiaomiControl.router_control.driver.quit()
    yield
    forget_network_cmd(target_ip='192.168.50.1')
    forget_network_cmd(target_ip='192.168.6.1')
    kill_setting()


def test_check_5g_saved_status():
    connect_ssid('ATC_ASUS_AX88U_5G', passwd)
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"
    connect_ssid('XiaomiAX3000_2G', passwd)
    assert pytest.dut.ping(hostname="192.168.6.1"), "Can't ping"
    enter_wifi_activity()
    pytest.dut.uiautomator_dump()
    assert 'saved' in pytest.dut.get_dump_info(),"connected ssid not saved"


