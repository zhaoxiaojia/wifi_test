# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/23 16:58
# @Author  : chao.li
# @File    : test_ac_str.py


import time
from src.test.stress import multi_stress

import pytest

from src.tools.usb_relay import UsbRelay

# the control by power usb
power = UsbRelay("COM9")
# the control by bt remote usb
bt = UsbRelay("COM6")

# set time to power on
power_on = 5
# set time to power off
power_off = 10
# how many times to repeat
repeat = 1000

'''
Test step

1:Dut power off few seconds
2:Dut power on few seconds 
3:Dut str on

repeat 1-3
'''


@pytest.fixture(autouse=True)
def setup_teardown():
    yield
    power.close()
    bt.close()


@multi_stress
def test_ac_str_switch(device):
    for _ in range(repeat):
        power.power_control('off', power_off)
        power.power_control('on', power_on)
        time.sleep(1)
        bt.break_make()
        time.sleep(10)
