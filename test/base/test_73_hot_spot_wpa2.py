#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_73_hot_spot_wpa2.py
# Time       ：2023/7/17 17:40
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import time

import pytest

from tools.connect_tool.adb import concomitant_dut

'''
测试步骤
1.进入设置，开启热点，设置加密方式为WPA2 PSK
2.远端设备连接SAP
'''


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.executer.open_hotspot()
    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()


@pytest.mark.hot_spot
def test_hotspot_wap2():
    ssid = pytest.executer.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.executer.set_hotspot(encrypt='WPA2 PSK')
    pytest.executer.wait_and_tap('Hotspot password', 'text')
    passwd = pytest.executer.u().d2(resourceId="android:id/edit").get_text()
    logging.info(passwd)
    time.sleep(1)
    pytest.executer.keyevent(4)
    cmd = pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd)
    logging.info(cmd)
    concomitant_dut.checkoutput(cmd)
    ipaddress = pytest.executer.wait_for_wifi_address(cmd, accompanying=True,target="192.168")[1]
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    pytest.executer.forget_network_cmd(ipaddress, accompanying=True)
