# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/14 9:20
# @Author  : chao.li
# @File    : test_bt_switch.py


import time
from src.test import multi_stress

from src.tools.router_tool.Router import Router

ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4G', ssid=ssid, wireless_mode='11n', channel='1', bandwidth='40 MHz',
                   authentication='Open System')

'''
Test step
1.Connect any AP,connect BT remote control
2.Do BT on/off stress test for about 12 hours.
3.Check wifi and BT status

Expected Result
3.WIFI works well,BT remote control works well.

'''


@multi_stress
def test_bt_switch(device):
    start_time = time.time()
    while time.time() - start_time < 3600 * 12:
        device.checkoutput(device.SVC_BLUETOOTH_DISABLE)
        time.sleep(2)
        device.checkoutput(device.SVC_BLUETOOTH_ENABLE)
        time.sleep(2)
