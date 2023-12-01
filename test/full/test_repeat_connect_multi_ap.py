# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_repeat_connect_multi_ap.py
# Time       ：2023/8/2 10:32
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
1.连接AP1；
2.连接另外一个AP2

输入正确的密码后开始连接，平台能自动断开与AP1的连接，而连接上AP2.
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
    ax88uControl.router_control.driver.quit()
    time.sleep(3)
    zte5400Control = ZTEax5400Control()
    zte5400Control.change_setting(router_zte)
    zte5400Control.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.forget_network_cmd(target_ip='192.168.2.1')
    pytest.executer.kill_setting()

@pytest.mark.multi_ap
def test_repeat_change_ap():
    pytest.executer.connect_ssid(asus_ssid_name, passwd,target='192.168.50')
    pytest.executer.connect_ssid(zte_ssid_name, passwd,target='192.168.2')
    for i in range(4):
        pytest.executer.connect_save_ssid(asus_ssid_name)
        assert pytest.executer.wait_for_wifi_address(target='192.168.50'),"Can't reconnect"
        pytest.executer.connect_save_ssid(zte_ssid_name)
        assert pytest.executer.wait_for_wifi_address(target='192.168.2'),"Can't reconnect"