# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/11/11 14:00
# @Author  : chao.li
# @File    : test_autoreboot_norouter.py
# @Project : wifi_test
# @Software: PyCharm


import time
from src.test.stress import multi_stress

'''
Test step
1.Connect any AP
2.Do autoreboot stress test for about 12 hours.
3.Check wifi status

Expected Result
3.WIFI works well,AP list display normal.

'''



@multi_stress
def test_autoreboot(device):
    start_time = time.time()
    while time.time() - start_time < 3600 * 12:
        device.reboot()
        device.wait_devices()
        device.wait_for_wifi_service()