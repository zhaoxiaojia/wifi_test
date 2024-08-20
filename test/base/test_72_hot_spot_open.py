#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_72_hot_spot_open.py
# Time       ：2023/7/17 17:11
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging

import pytest

from tools.connect_tool.adb import concomitant_dut

'''
测试步骤
1.进入设置，开启热点，设置加密方式为OPEN
2.远端设备连接SAP
'''
@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.dut.open_hotspot()
    logging.info('setup done')
    yield
    pytest.dut.close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_open():
    ssid = pytest.dut.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.dut.set_hotspot(encrypt='None')
    cmd = pytest.dut.CMD_WIFI_CONNECT_OPEN.format(ssid)
    logging.info(cmd)
    concomitant_dut.checkoutput(cmd)
    ipaddress = pytest.dut.wait_for_wifi_address(cmd, accompanying=True,target="192.168")[1]
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    pytest.dut.forget_network_cmd(ipaddress, accompanying=True)
