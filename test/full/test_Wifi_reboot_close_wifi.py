#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/23 10:13
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_reboot_close_pytest.dut.py
# @Software: PyCharm




import logging
import re
import time
from test import (close_wifi, config_yaml, enter_wifi_activity, open_wifi,
                  wait_for_wifi_service)

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
    open_wifi()
    pytest.dut.reboot()
    pytest.dut.wait_devices()


def test_reboot_close_wifi():
    close_wifi()
    pytest.dut.reboot()
    pytest.dut.wait_devices()
    wait_for_wifi_service()
    enter_wifi_activity()
    pytest.dut.uiautomator_dump()
    assert 'Available networks' not in pytest.dut.get_dump_info(), 'Wifi is not disable'
