#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/5/12 09:53
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_non_dfs_swtich_to_dfs.py
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

Switch from Non DFS channel to onther DFS channel
(从非DFS信道切换到另一个DFS信道)

1.Set AP 5G to Non DFS channel(make sure DUT also support this channel)
2.DUT connect AP 5G SSID
3.DUT ping AP all the time
4.Switch AP from Non DFS channel to another DFS channel
5.check DUT wifi state and ping state

5.DUT will disconnect with AP, and after one minutes, DUT will reasociate AP again and ping AP sucessfully.
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
    ax88uControl.change_setting(router_non_dfs)
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_non_dfs_switch_to__dfs():
    connect_ssid(ssid, passwd=passwd)
    assert wait_for_wifi_address(), "Connect fail"
    ax88uControl.change_setting(router_dfs)
    ax88uControl.router_control.driver.quit()
    time.sleep(30)
    assert wait_for_wifi_address(), "reconnect fail"
