# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/22 17:12
# @Author  : Chao.li
# @File    : test_Wifi_reconnect_forget_ssid.py
# @Project : python
# @Software: PyCharm


import logging
import os
import time

import pytest
from test import (Router, connect_ssid, find_ssid, forget_ssid,
                        kill_setting, wait_for_wifi_address)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.yamlTool import yamlTool

'''
测试步骤
忘记5G网络重新连接

1.Dut connect AP1-5G；
2.Enter wifi list ，forget the current network
3.connect the AP again.”
4.Play online video.

3.DUT can connect the forget AP success
4.Play online video success
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = '12345678'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='自动', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    # connect wifi
    cmd = pytest.executer.CMD_WIFI_CONNECT.format('ATC_ASUS_AX88U_5G', 'wpa2', '12345678')
    pytest.executer.checkoutput(cmd)
    wait_for_wifi_address(cmd)
    yield


def test_connect_forget_ssid():
    forget_ssid(ssid)
    kill_setting()
    assert connect_ssid(ssid, passwd=passwd), "Can't reconnect"
