# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/11/6 10:39
# @Author  : chao.li
# @File    : test_T7717132.py
# @Project : wifi_test
# @Software: PyCharm


import pytest
import time
from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
Preconditions:
1.WPA2 - AES
2.Password: 63 characters length

Steps
1) Go to Settings > Network > Wireless
2) Scan
3) Select scan again
4) Connect to WiFi

Expected Result
Verify that DUT can scan and connect
'''

ssid = 'ATC_ASUS_AX88U'
passwd = '123456789012345678901234567890123456789012345678901234567890123'
router_2g = Router(band='2.4G', ssid=ssid, wireless_mode='11n', channel='1', bandwidth='20 MHz',
                   security_protocol='WPA2-Personal')


ax88uControl = Asusax88uControl()


@pytest.mark.wifi_connect
@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl.change_setting(router_2g)
    time.sleep(10)
    yield


def test_Scan_Connect():
    pytest.dut.roku.wifi_conn()