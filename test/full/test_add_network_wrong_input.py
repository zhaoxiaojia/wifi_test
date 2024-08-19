#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/5/30 11:00
# @Author  : chao.li
# @Site    :
# @File    : test_add_network_wrong_input.py
# @Software: PyCharm



import logging
import os
import time

import pytest
from test import (Router, add_network, forget_network_cmd,
                        kill_setting, wait_for_wifi_address)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
添加WIFI网络

添加错误的网络信息

输入错误的网络信息，检查是否能添加成功

如果输入的信息不正确，选择添加后的SSID连接，平台不能正常的连接上。
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


def test_add_network_wrong_input():
    try:
        add_network('wronginput', 'None')
        assert False,"Should not get ip address"
    except AssertionError:
        assert True
