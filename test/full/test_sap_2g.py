#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/12 10:59
# @Author  : chao.li
# @Site    :
# @File    : test_sap_2g.py
# @Software: PyCharm



import logging
import time
from test import (accompanying_dut, close_hotspot, forget_network_cmd,
                  kill_moresetting, open_hotspot, wait_for_wifi_address)

import pytest

'''
测试步骤
2.4G

设置SAPband为2.4G

可以连接成功
'''

@pytest.fixture(autouse=True)
def setup_teardown():
    open_hotspot()
    logging.info('setup done')
    yield
    close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_2g():
    ssid = pytest.dut.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.dut.wait_and_tap('AP Band', 'text')
    pytest.dut.wait_element('2.4 GHz Band', 'text')
    pytest.dut.wait_and_tap('2.4 GHz Band', 'text')
    pytest.dut.wait_element('AP Band', 'text')
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
    accompanying_dut.checkoutput(cmd)
    ipaddress = wait_for_wifi_address(cmd, accompanying=True)[1]
    assert 'freq: 2' in accompanying_dut.checkoutput(pytest.dut.IW_LINNK_COMMAND), "Doesn't conect 2g "
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    forget_network_cmd(ipaddress, accompanying=True)
