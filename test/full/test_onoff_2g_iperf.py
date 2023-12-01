#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_onoff_2g_iperf.py
# Time       ：2023/7/25 9:19
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import os
import time

import pytest

from Iperf import Iperf
from Router import Router
from tools.Asusax88uControl import Asusax88uControl

'''
测试配置

1.连接2.4Gwifi;
2.CH6信道，开关wifi后打流
3.2循环20次。

'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'

router_ch6 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='6', bandwidth='20/40 MHz',
                    authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()
iperf = Iperf()


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl.change_setting(router_ch6)
    ax88uControl.router_control.driver.quit()
    logging.info(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
    pytest.executer.checkoutput(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


def test_change_channel_iperf():
    for _ in range(2):
        pytest.executer.close_wifi()
        pytest.executer.open_wifi()
        pytest.executer.wait_for_wifi_address()
        assert iperf.run_iperf(), "Can't run iperf success"
