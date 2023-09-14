# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_smart_connect_4k.py
# Time       ：2023/9/14 10:52
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""




import logging
import re
import time

import pytest

from tools.Asusax88uControl import Asusax88uControl
from Router import Router

'''
测试步骤
1.设置路由器SSID"ATC_ASUS_AX88U"，开启smart connect
2.播放youtube
'''

ssid = 'ATC_ASUS_AX88U'
passwd = 'test1234'
router = Router(band='2.4 GHz', ssid=ssid, wireless_mode='Legacy', channel='自动', bandwidth='20 MHz',
                authentication_method='WPA2-Personal', wpa_passwd=passwd,
                smart_connect=True)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.home()
    pytest.executer.forget_ssid(ssid)


def test_smart_connect():
    pytest.executer.playback_youtube(sleep_time=3600*24)