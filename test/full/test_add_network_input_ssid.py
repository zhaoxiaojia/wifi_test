#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_add_network_input_ssid.py
# Time       ：2023/7/24 9:47
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
添加WIFI网络

SSID输入

输入网络SSID

能输入成功
'''

ssid = 'ATC_ASUS_AX88U_5G'
router_2g = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='157', bandwidth='80 MHz',
                   authentication_method='Open System')


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_tvsetting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


def test_add_network_input_ssid():
    pytest.executer.add_network(ssid, 'None')
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"
