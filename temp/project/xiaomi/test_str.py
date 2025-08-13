# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/23 17:31
# @Author  : chao.li
# @File    : test_str.py


import time
from src.test import multi_stress

import pytest

from src.tools.usb_relay import UsbRelay

# the control by power usb
bt = UsbRelay("COM6")

# set time to power on
str_sleep = 5
# set time to power off
str_wake = 5
# how many times to repeat
repeat = 1000
# test address
address = "192.168.50.1"

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
        bt.break_make()
        time.sleep(str_sleep)
        bt.break_make()
        time.sleep(str_wake)
        device.ping(address)
