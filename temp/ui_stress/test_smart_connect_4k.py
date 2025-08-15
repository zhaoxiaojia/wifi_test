# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_smart_connect_4k.py
# Time       ：2023/9/14 10:52
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试步骤
1.设置路由器SSID"ATC_ASUS_AX88U"，开启smart connect
2.播放youtube
'''

ssid = 'ATC_ASUS_AX88U'
passwd = 'test1234'
router = Router(band='2.4G', ssid=ssid, wireless_mode='Legacy', channel='自动', bandwidth='20 MHz',
                authentication='WPA2-Personal', wpa_passwd=passwd,
                smart_connect=True)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.home()
    pytest.dut.forget_ssid(ssid)


def test_smart_connect():
    pytest.dut.playback_youtube(sleep_time=3600*24)