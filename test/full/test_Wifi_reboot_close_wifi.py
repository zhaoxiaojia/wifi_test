#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/23 10:13
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_reboot_close_pytest.executer.py
# @Software: PyCharm




import logging
import re
import time

import pytest
from test import (close_wifi, config_yaml, enter_wifi_activity,
                        open_wifi, wait_for_wifi_service)

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
    pytest.executer.reboot()
    pytest.executer.wait_devices()


def test_reboot_close_wifi():
    close_wifi()
    pytest.executer.reboot()
    pytest.executer.wait_devices()
    wait_for_wifi_service()
    enter_wifi_activity()
    pytest.executer.uiautomator_dump()
    assert 'Available networks' not in pytest.executer.get_dump_info(), 'Wifi is not disable'
