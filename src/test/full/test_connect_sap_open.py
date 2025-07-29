#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/14 10:04
# @Author  : chao.li
# @Site    :
# @File    : test_connect_sap_open.py
# @Software: PyCharm



import logging
from src.test import (accompanying_dut, close_hotspot, forget_network_cmd,
                      kill_moresetting, open_hotspot, wait_for_wifi_address)

import pytest

'''
测试步骤
Open

SoftAP安全性设置（Open）

设为Open时，连接时不需要密码

'''
@pytest.fixture(autouse=True)
def setup_teardown():
    open_hotspot()
    logging.info('setup done')
    yield
    close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_open():
    ssid = pytest.dut.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.dut.wait_and_tap('Security', 'text')
    pytest.dut.wait_element('None', 'text')
    pytest.dut.wait_and_tap('None', 'text')
    pytest.dut.wait_element('Security', 'text')
    cmd = pytest.dut.CMD_WIFI_CONNECT_OPEN.format(ssid)
    logging.info(cmd)
    accompanying_dut.checkoutput(cmd)
    ipaddress = wait_for_wifi_address(cmd, accompanying=True)[1]
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    forget_network_cmd(ipaddress, accompanying=True)
