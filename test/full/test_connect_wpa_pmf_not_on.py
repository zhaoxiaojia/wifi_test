# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_wpa_pmf_not_on.py
# Time       ：2023/7/31 17:07
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

'''
测试配置
PMF非强制启用 WPA加密

１.AP set PMF PMF非强制启用，and secutiy WPA;
2.DUT connect ap and play online video.

连接成功
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20 MHz',
                   authentication_method='WPA/WPA2-Personal', wpa_passwd=passwd, protect_frame='非强制启用')


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_tvsetting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


@pytest.mark.wifi_connect
def test_connect_wpa_pmf_not_on():
    assert pytest.executer.connect_ssid(ssid, passwd), "Can't connect"
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"
