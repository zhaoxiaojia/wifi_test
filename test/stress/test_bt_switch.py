# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/14 9:20
# @Author  : chao.li
# @File    : test_bt_switch.py

# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/12 13:50
# @Author  : chao.li
# @File    : test_wifi_switch.py

import logging
import time
from test.stress import multi_stress

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='Open System')

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
