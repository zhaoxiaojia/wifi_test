# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_reboot_close_wifi.py
# Time       ：2023/8/2 9:48
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


import logging
import re
import time

import pytest

'''
测试步骤
关闭WiFi重启设备

1.手动关闭wifi；
2.重启DUT

关闭wifi后，无法搜索到AP
重启后默认关闭
'''


@pytest.fixture(autouse=True)
def setup_teardown():
    yield
    pytest.executer.open_wifi()
    pytest.executer.reboot()
    pytest.executer.wait_devices()

@pytest.mark.reset_dut
def test_reboot_close_wifi():
    pytest.executer.close_wifi()
    pytest.executer.reboot()
    pytest.executer.wait_devices()
    try:
        pytest.executer.wait_for_wifi_service()
    except EnvironmentError as e:
        ...
    pytest.executer.enter_wifi_activity()
    pytest.executer.uiautomator_dump()
    assert 'Available networks' not in pytest.executer.get_dump_info(), 'Wifi is not disable'
