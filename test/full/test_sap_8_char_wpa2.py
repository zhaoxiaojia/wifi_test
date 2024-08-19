#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/8 14:07
# @Author  : chao.li
# @Site    :
# @File    : test_sap_8_char_wpa2.py
# @Software: PyCharm



import logging
import time

import pytest
from test import (accompanying_dut,  close_hotspot, forget_network_cmd, kill_moresetting,
                        open_hotspot, wait_for_wifi_address)

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
    open_hotspot()
    logging.info('setup done')
    yield
    close_hotspot()

@pytest.mark.hot_spot
def test_8_char_wpa2():
    ssid = pytest.executer.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.executer.wait_and_tap('Security', 'text')
    pytest.executer.wait_element('WPA2 PSK', 'text')
    pytest.executer.wait_and_tap('WPA2 PSK', 'text')
    pytest.executer.wait_element('Security', 'text')
    pytest.executer.wait_and_tap('Hotspot password', 'text')
    pytest.executer.u().d2(resourceId="android:id/edit").clear_text()
    pytest.executer.checkoutput(f'input text {passwd}')
    pytest.executer.uiautomator_dump()
    assert passwd in pytest.executer.get_dump_info(), "passwd doesn't currently"
    time.sleep(1)
    pytest.executer.keyevent(66)
    cmd = pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd)
    logging.info(cmd)
    accompanying_dut.checkoutput(cmd)
    wait_for_wifi_address(cmd, accompanying=True)
    ipaddress = wait_for_wifi_address(cmd, accompanying=True)[1]
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    forget_network_cmd(ipaddress, accompanying=True)
