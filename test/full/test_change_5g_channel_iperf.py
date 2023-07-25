#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_change_5g_channel_iperf.py
# Time       ：2023/7/24 11:14
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import os
import time

import pytest

from tools.Asusax88uControl import Asusax88uControl
from Router import Router
from Iperf import Iperf

'''
测试配置
1.连接5Gwifi;
2.切换不同信道进行打流，36-100-161
3.循环20次。

'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_ch36 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='36', bandwidth='40 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_ch100 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='100', bandwidth='40 MHz',
                      authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_ch161 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='161', bandwidth='40 MHz',
                      authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()
iperf = Iperf()


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl.change_setting(router_ch100)
    time.sleep(150)
    yield
    ax88uControl.router_control.driver.quit()
    pytest.executer.kill_tvsetting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


def test_change_channel_iperf():
    for i in [router_ch36, router_ch100, router_ch161] * 7:
        ax88uControl.change_setting(i)
        logging.info(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
        pytest.executer.checkoutput(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
        pytest.executer.wait_for_wifi_address()
        assert iperf.run_iperf(), "Can't run iperf success"
