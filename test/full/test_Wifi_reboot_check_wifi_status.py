#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/23 09:52
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_reboot_check_wifi_status.py
# @Software: PyCharm



import logging
import re
import time
from test import config_yaml, enter_wifi_activity, wait_for_wifi_service

import pytest

'''
测试步骤
WIFI默认状态检查

进入settings内wifi,检查默认状态

wifi是默认成“打开”的
'''

WIFI_ENABLE_STRING = 'Wifi is enabled'



@pytest.fixture(autouse=True)
def setup_teardown():
    enter_wifi_activity()
    pytest.dut.uiautomator_dump()
    assert 'Available networks' in pytest.dut.get_dump_info(), 'Wifi is not enable'
    yield
    pytest.dut.reboot()
    pytest.dut.wait_devices()


def test_check_status_after_reboot():
    pytest.dut.reboot()
    pytest.dut.wait_devices()
    wait_for_wifi_service()
    enter_wifi_activity()
    pytest.dut.uiautomator_dump()
    assert 'Available networks' in pytest.dut.get_dump_info(), 'Wifi is not enable'
