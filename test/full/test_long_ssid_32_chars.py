#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_long_ssid_32_chars.py
# Time       ：2023/7/25 9:07
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging
import os
import time

import pytest

from Router import Router
from tools.Asusax88uControl import Asusax88uControl

'''
测试步骤
SSID 为32个字符

1.设置SAP SSID为32个字符"12345678901234567890123456789012"

可以保存成功，并能正确显示
'''


ssid = "12345678901234567890123456789012"


router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='自动', bandwidth='20 MHz',
                   authentication_method='Open System')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd()
    pytest.executer.kill_setting()

@pytest.mark.wifi_connect
def test_connect_32_chars_ssid():
    assert pytest.executer.connect_ssid(ssid), "Can't connect"