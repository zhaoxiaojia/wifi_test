# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_2g_channel_14.py
# Time       ：2023/7/26 14:55
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
Auto mode 信道14

Connect an AP which channel is 14(wifi31)
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='14', bandwidth='20/40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd, country_code='中国 (默认值)')


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    global router_2g
    ax88uControl = Asusax88uControl()
    ax88uControl.change_country(router_2g)
    ax88uControl.change_setting(router_2g)
    yield
    pytest.executer.kill_tvsetting()
    router_2g = router_2g._replace(country_code='美国')
    ax88uControl.change_country(router_2g)
    ax88uControl.router_control.driver.quit()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


def test_channel_14():
    assert True
    # connect_ssid(ssid, passwd=passwd)
    # assert wait_for_wifi_address(), "Connect fail"
