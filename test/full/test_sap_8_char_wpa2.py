#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_sap_8_char_wpa2.py
# Time       ：2023/7/25 9:41
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging
import time

import pytest

from ADB import concomitant_dut

'''
测试步骤
密码8个数字英文组合-WPA2

1.进入SoftAP设置界面；
2.设置任意WPA2加密的AP
3.进入密码输入界面后输入8个数字英文的组合并确认
4.添加配合终端设备

密码长度8-64，其余个数的字符，应该无法继续输入或灰化保存按纽
'''

passwd = 'abcd1234'

@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.executer.open_hotspot()
    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()

@pytest.mark.hot_spot
def test_8_char_wpa2():
    ssid = pytest.executer.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.executer.set_hotspot(passwd=passwd,encrypt='WPA2 PSK')
    cmd = pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd)
    logging.info(cmd)
    concomitant_dut.checkoutput(cmd)
    pytest.executer.wait_for_wifi_address(cmd, accompanying=True)
    ipaddress = pytest.executer.wait_for_wifi_address(cmd, accompanying=True)[1]
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    pytest.executer.forget_network_cmd(ipaddress, accompanying=True)
