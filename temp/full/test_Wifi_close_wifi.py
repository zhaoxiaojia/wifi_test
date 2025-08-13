#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/23 10:03
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_close_pytest.dut.py
# @Software: PyCharm


from src.test import (close_wifi, enter_wifi_activity, kill_setting, open_wifi,
                      wifi_onoff_tag)

import pytest

'''
测试步骤
关闭WiFi

手动关闭wifi

关闭wifi后，无法搜索到AP
'''


@pytest.fixture(autouse=True)
def setup_teardown():
    yield
    open_wifi()


def test_close_wifi():
    close_wifi()
    enter_wifi_activity()
    pytest.dut.uiautomator_dump()
    assert wifi_onoff_tag not in pytest.dut.get_dump_info(), "Can't close wifi"
