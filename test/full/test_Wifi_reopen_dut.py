#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/19 15:44
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_reopen_dut.py
# @Software: PyCharm



import logging
import os
import re
import time

import pytest
from test import (Router, connect_ssid, forget_network_cmd,
                        kill_setting, youtube,
                        wait_for_wifi_address, wait_for_wifi_service)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
连接AC-5G
AC on/off DUT

1.AC on/off DUT
2.Play online video.

1.WiFi will auto reconnected
2.Can play online video
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='165', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    # kill_setting()
    # forget_network_cmd(target_ip='192.168.50.1')


def test_reopen_dut():
    connect_ssid(ssid,passwd)
    youtube.playback_youtube()
    time.sleep(30)
    pytest.executer.reboot()
    wait_for_wifi_service()
    youtube.playback_youtube()
    time.sleep(30)

