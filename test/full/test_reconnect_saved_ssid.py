# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_reconnect_saved_ssid.py
# Time       ：2023/8/2 10:07
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import time

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.ZTEax5400Control import ZTEax5400Control

'''
测试步骤

连接网络

选择“连接”选项

自动连接上AP2
'''

asus_ssid_name = 'ATC_ASUS_AX88U'
zte_ssid_name = 'XiaomiAX3000_5G'
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


@pytest.mark.mul_router
def test_repeat_change_ap():
    pytest.executer.connect_ssid(asus_ssid_name, passwd, target='192.168.50')
    pytest.executer.connect_ssid(zte_ssid_name, passwd, target='192.168.2')
    pytest.executer.connect_save_ssid(asus_ssid_name)
