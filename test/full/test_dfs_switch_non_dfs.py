# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_dfs_switch_non_dfs.py
# Time       ：2023/8/1 15:30
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

Switch from Non-whether DFS channel to anther Non DFS channel
(从DFS信道切换到另一个非DFS信道)

1.Set AP 5G to Non-whether DFS channel(make sure DUT also support this channel)
2.DUT connect AP 5G SSID
3.DUT ping AP all the time
4.Switch AP DFS channel to another Non DFS channel
5.check DUT wifi state and ping state

4.DUT will disconnect in a short interval, and then reassociated success immediately
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'

router_dfs = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='52', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_non_dfs = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='36', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)
ax88uControl = Asusax88uControl()

@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl.change_setting(router_dfs)
    time.sleep(30)
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd()

@pytest.mark.wifi_connect
def test_dfs_switch_to_non_dfs():
    pytest.executer.connect_ssid(ssid, passwd=passwd)
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"
    ax88uControl.change_setting(router_non_dfs)
    ax88uControl.router_control.driver.quit()
    time.sleep(30)
    assert pytest.executer.wait_for_wifi_address(), "reconnect fail"
