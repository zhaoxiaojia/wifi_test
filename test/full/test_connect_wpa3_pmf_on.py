# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_wpa3_pmf_on.py
# Time       ：2023/8/1 13:37
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import os
import time

import pytest

from Router import Router
from tools.Asusax88uControl import Asusax88uControl

'''
测试配置
PMF 强制启用 WPA3加密

１.AP set PMF PMF强制启用，and secutiy WPA3;
2.DUT connect ap and play online video.

连接成功
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20 MHz',
                   authentication_method='WPA3-Personal', wpa_passwd=passwd,protect_frame='强制启用')



@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd()

@pytest.mark.wifi_connect
def test_connect_wpa3_pmf__on():
    pytest.executer.connect_ssid(ssid, passwd)
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"


