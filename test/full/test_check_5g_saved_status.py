# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_check_5g_saved_status.py
# Time       ：2023/7/26 16:29
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import re
import time

import pytest

from tools.Asusax88uControl import Asusax88uControl
from tools.ZTEax5400Control import ZTEax5400Control
from Router import Router
'''
测试步骤
5GSaved的网络检查

1.Dut connect AP1-5G；
2.Dut connect AP2-5G
3.Dut connect AP!-5G

3.When reconnect AP1-5G ->Exist [Connect]\[Forget network]->If select  connect ap, dut will reconnect successfully, if Select forget, will get, dut will forget the network
'''

asus_ssid = 'ATC_ASUS_AX88U_5G'
zte_ssid = 'ZTEax5400_5G'
passwd = '12345678'
asus_5g = Router(band='5 GHz', ssid=asus_ssid, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)
zte_5g = Router(band='5 GHz', ssid=zte_ssid, wireless_mode='802.11 a/n/ac', channel='161',
                   bandwidth='20MHz/40MHz/80MHz',
                   authentication_method='WPA-PSK/WPA2-PSK', wpa_passwd='12345678')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    zteControl = ZTEax5400Control()
    ax88uControl.change_setting(asus_5g)
    time.sleep(1)
    zteControl.change_setting(zte_5g)
    ax88uControl.router_control.driver.quit()
    zteControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.forget_network_cmd(target_ip='192.168.2.1')
    pytest.executer.kill_tvsetting()

@pytest.mark.mul_router
def test_check_5g_saved_status():
    pytest.executer.connect_ssid(asus_ssid, passwd)
    pytest.executer.connect_ssid(zte_ssid, passwd,target="192.168.2")
    pytest.executer.enter_wifi_activity()
    pytest.executer.uiautomator_dump()
    assert 'saved' in pytest.executer.get_dump_info() or 'Saved' in pytest.executer.get_dump_info(), "connected ssid not saved"


