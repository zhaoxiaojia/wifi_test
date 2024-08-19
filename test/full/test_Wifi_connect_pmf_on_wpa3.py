# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/17 10:54
# @Author  : Chao.li
# @File    : test_Wifi_connect_pmf_on_wpa3.py
# @Project : python
# @Software: PyCharm



import logging
import os
import time

import pytest
from test import (Router, connect_ssid, forget_network_cmd,
                        kill_setting, wait_for_wifi_address)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

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
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_connect_wpa3_pmf__on():
    connect_ssid(ssid, passwd)
    assert wait_for_wifi_address(), "Connect fail"


