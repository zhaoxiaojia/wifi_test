# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/11/6 10:39
# @Author  : chao.li
# @File    : test_wifi_switch.py
# @Project : wifi_test
# @Software: PyCharm


from test.project.roku import *
import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

'''
Pre step:
1.Set asus router 2.4 Ghz ssid ATC_ASUS_AX88U open system
2.connect asus 

Test step
1.change router 2.4 g
2.change router 5g

Expected Result
'''

ssid = 'ATC_ASUS_AX88U'
ssid_bat = 'ATC_ASUS_AX88U_bat'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='11n', channel='1', bandwidth='20 MHz',
                   authentication_method='Open System')

router_5g = Router(band='5 GHz', ssid=ssid_bat, wireless_mode='11ac', channel='36', bandwidth='80 MHz',
                   authentication_method='Open System')

ax88uControl = Asusax88uControl()


@pytest.mark.wifi_connect
@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl.change_setting(router_2g)
    ax88uControl.change_setting(router_5g)
    time.sleep(10)
    yield


def test_wifi_switch():
    start = time.time()
    while (time.time() - start < 3600 * 4 * 24):
        ax88uControl.change_setting(Router(band='2.4 Ghz', ssid=ssid))
        ax88uControl.change_setting(Router(band='5 Ghz', ssid=ssid_bat))
        time.sleep(60)
        ax88uControl.change_setting(Router(band='5 Ghz', ssid=ssid))
        ax88uControl.change_setting(Router(band='2.4 Ghz', ssid=ssid_bat))
        time.sleep(60)
