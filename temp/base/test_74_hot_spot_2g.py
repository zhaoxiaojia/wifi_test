#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_74_hot_spot_2g.py
# Time       ：2023/7/18 9:48
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import time

import pytest

from src.tools.connect_tool.adb import concomitant_dut

'''
测试步骤
设置SAPband为2.4G
'''


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.dut.open_hotspot()
    logging.info('setup done')
    yield
    pytest.dut.close_hotspot()


@pytest.mark.hot_spot
def test_hotspot_2g():
    ssid = pytest.dut.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.dut.set_hotspot(type='2.4G Band')
    pytest.dut.uiautomator_dump()
    if 'WPA2 PSK' in pytest.dut.get_dump_info():
        # wpa2 need passwd
        pytest.dut.wait_and_tap('Hotspot password', 'text')
        passwd = pytest.dut.u().d2(resourceId="android:id/edit").get_text()
        logging.info(passwd)
        time.sleep(1)
        pytest.dut.keyevent(4)
        pytest.dut.keyevent(4)
        cmd = pytest.dut.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd)
    else:
        # none doesn't need passwd
        cmd = pytest.dut.CMD_WIFI_CONNECT_OPEN.format(ssid)
    logging.info(cmd)
    concomitant_dut.checkoutput(cmd)
    ipaddress = pytest.dut.wait_for_wifi_address(cmd, accompanying=True,target="192.168")[1]
    logging.info(concomitant_dut.checkoutput(pytest.dut.IW_LINNK_COMMAND))
    assert 'freq: 2' in concomitant_dut.checkoutput(pytest.dut.IW_LINNK_COMMAND), "Doesn't conect 2g "
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    pytest.dut.forget_network_cmd(ipaddress, accompanying=True)
