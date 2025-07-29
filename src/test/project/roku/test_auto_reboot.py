# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/11/6 14:31
# @Author  : chao.li
# @File    : test_auto_reboot.py
# @Project : wifi_test
# @Software: PyCharm


import logging
import time
from os import times

import pytest

'''
Pre step:
1.Set asus router 2.4 Ghz ssid ATC_ASUS_AX88U open system
2.connect asus 

Test step
1.reboot dut
2.telnet dut

Expected Result
'''


def test_auto_reboot():
    start = time.time()
    while (time.time() - start < 3600 * 24 * 4):
        pytest.dut.tn.open(pytest.dut.dut_ip, port=23)
        pytest.dut.checkoutput('reboot')
        time.sleep(60)
        pytest.dut.checkoutput('iw dev')
