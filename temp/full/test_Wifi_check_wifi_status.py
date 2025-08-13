#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/21 15:04
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_check_wifi_status.py
# @Software: PyCharm


from src.test import close_wifi, enter_wifi_activity, open_info

import pytest

'''
测试步骤
WIFI默认状态检查

进入settings内wifi,检查默认状态

wifi是默认成“打开”的
'''

WIFI_ENABLE_STRING = 'Wifi is enabled'


def test_check_wifi_status():
    enter_wifi_activity()
    pytest.dut.uiautomator_dump()
    assert 'Available networks' in pytest.dut.get_dump_info(),'Wifi is not enable'