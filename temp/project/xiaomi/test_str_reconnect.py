# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/11/25 19:07
# @Author  : chao.li
# @File    : test_str_reconnect.py


import time
from src.test import multi_stress

import pytest

from src.tools.usb_relay import UsbRelay

# the control by power usb
bt = UsbRelay("COM10")

# set time to power on
str_sleep = 5
# set time to power off
str_wake = 5
# how many times to repeat
repeat = 1000
# test address
address = "192.168.50.1"

ssid = 'AX88U-2G'
passwd = '12345678'
security = 'wpa2'
'''
Test step

1:Dut sleep few seconds
2:Dut wake few seconds 
3:Ping 
repeat 1-3
'''


@pytest.fixture(autouse=True)
def setup_teardown():
    yield
    bt.close()


@multi_stress
def test_str(device):
    for _ in range(repeat):
        device.forget_wifi()
        bt.break_make(port=2)
        time.sleep(str_sleep)
        bt.break_make(port=2)
        time.sleep(str_wake)
        device.connect_wifi(ssid, passwd, security)
        device.ping(address)
