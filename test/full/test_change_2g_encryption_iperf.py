#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_change_2g_encryption_iperf.py
# Time       ：2023/7/24 15:38
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging

import pytest

from tools.Iperf import Iperf
from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置

不同加密方式切换打流

1.连接2.4Gwifi;
2.CH6信道，切换不同加密方式，OPEN-WAP1-WAP2-WAP2
3..2循环20次。

TPS正常，无掉零，无断流
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_wpa2 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20/40 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_wpa3 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='6', bandwidth='20/40 MHz',
                     authentication_method='WPA3-Personal', wpa_passwd=passwd)
router_open = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='11', bandwidth='20/40 MHz',
                     authentication_method='Open System')

ax88uControl = Asusax88uControl()
iperf = Iperf()

@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router

    yield
    ax88uControl.router_control.driver.quit()
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


def test_change_encryption_iperf():
    for i in [router_wpa2, router_wpa3, router_open] * 7:
        ax88uControl.change_setting(i)
        logging.info(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
        if i.authentication_method == 'Open System':
            pytest.executer.checkoutput(pytest.executer.CMD_WIFI_CONNECT_OPEN.format(ssid))
        if i.authentication_method == 'WPA2-Personal':
            pytest.executer.checkoutput(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
        if i.authentication_method == 'WPA3-Personal':
            pytest.executer.checkoutput(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa3', passwd))
        pytest.executer.wait_for_wifi_address()
        assert iperf.run_iperf(), "Can't run iperf success"
