#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/14 13:55
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_11n_channel_132.py
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
11n mode 信道132 40MHz带宽

Connect an AP which channel is 5G n-44-band 132
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='132', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    time.sleep(30)
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_channel_132():
    connect_ssid(ssid, passwd=passwd)
    assert wait_for_wifi_address(), "Connect fail"
