#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/5/29 16:23
# @Author  : chao.li
# @Site    :
# @File    : test_add_network_input_ssid.py
# @Software: PyCharm



import logging
import os
import time
from test import (Router, add_network, forget_network_cmd, kill_setting,
                  wait_for_wifi_address)

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

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
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_add_network_input_ssid():
    add_network(ssid, 'None')
    assert wait_for_wifi_address(), "Connect fail"
