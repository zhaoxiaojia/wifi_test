#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/21 14:08
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_connect_save_ssid.py
# @Software: PyCharm


import time
from src.test import (Router, connect_ssid, find_ssid, forget_network_cmd,
                      kill_setting, wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.ZTEax5400Control import ZTEax5400Control

'''
测试步骤
2.4G自动连接相同名字的Saved的网络

1.DUT connect AP1-2.4G；
2.DUT connect AP2-2.4G;
3.Enter wifi list idle-> Current connected wifi->select“Forget network”
3.Play online video.

2.Can auto reconnect the saved wifi
3.Can Play online video
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
    forget_network_cmd(target_ip='192.168.50.1')
    forget_network_cmd(target_ip='192.168.2.1')
    kill_setting()


def test_repeat_change_ap():
    connect_ssid(asus_ssid_name, passwd,target='192.168.50')
    kill_setting()
    connect_ssid(zte_ssid_name, passwd,target='192.168.2')
    kill_setting()
