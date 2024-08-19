#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/12 11:05
# @Author  : chao.li
# @Site    :
# @File    : test_sap_5g.py
# @Software: PyCharm



import logging
import time

import pytest
from test import (accompanying_dut,  close_hotspot, forget_network_cmd, kill_moresetting,
                        open_hotspot, wait_for_wifi_address)

'''
测试步骤
5G

设置SAP band为5G

可以连接成功
'''

@pytest.fixture(autouse=True)
def setup_teardown():
    open_hotspot()
    logging.info('setup done')
    yield
    close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_5g():
    ssid = pytest.executer.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.executer.wait_and_tap('AP Band', 'text')
    pytest.executer.wait_element('5.0 GHz Band', 'text')
    pytest.executer.wait_and_tap('5.0 GHz Band', 'text')
    pytest.executer.wait_element('AP Band', 'text')
    pytest.executer.uiautomator_dump()
    if 'WPA2 PSK' in pytest.executer.get_dump_info():
        # wpa2 need passwd
        pytest.executer.wait_and_tap('Hotspot password', 'text')
        passwd = pytest.executer.u().d2(resourceId="android:id/edit").get_text()
        logging.info(passwd)
        time.sleep(1)
        pytest.executer.keyevent(4)
        pytest.executer.keyevent(4)
        cmd = pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd)
    else:
        # none doesn't need passwd
        cmd = pytest.executer.CMD_WIFI_CONNECT_OPEN.format(ssid)
    logging.info(cmd)
    accompanying_dut.checkoutput(cmd)
    ipaddress = wait_for_wifi_address(cmd, accompanying=True)[1]
    assert 'freq: 5' in accompanying_dut.checkoutput(accompanying_dut.IW_LINNK_COMMAND), "Doesn't conect 5g "
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    forget_network_cmd(ipaddress, accompanying=True)
