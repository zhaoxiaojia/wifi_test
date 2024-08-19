#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/5/29 16:51
# @Author  : chao.li
# @Site    :
# @File    : test_add_network_wep.py
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

WEP加密方式

添加安全性选择 加密方式-WEP的网络

能添加成功
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='Legacy', channel='1', bandwidth='20 MHz',
                   authentication_method='Shared Key', wep_passwd=passwd,wep_encrypt='WEP-64bits')



@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_add_network_wep():
    add_network(ssid, 'WEP',passwd=passwd)
    assert wait_for_wifi_address(), "Connect fail"
