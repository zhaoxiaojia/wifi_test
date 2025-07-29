#!/usr/bin/env python 
# -*- coding: utf-8 -*- 

"""
# File       : test_05_close_wifi.py
# Time       ：2023/7/13 10:08
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging
import os
import time

import pytest

'''
测试步骤
1.进入设置-无线网络
2.WIFI开关为打开状态，点击WIFI开关
'''


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.dut.open_wifi()
    yield
    pytest.dut.open_wifi()


def test_close_wifi():
    pytest.dut.close_wifi()
    pytest.dut.start_activity(*pytest.dut.SETTING_ACTIVITY_TUPLE)
    pytest.dut.wait_element('Network & Internet', 'text')
    pytest.dut.wait_and_tap('Network & Internet', 'text')
    pytest.dut.uiautomator_dump()
    assert pytest.dut.WIFI_BUTTON_TAG not in pytest.dut.get_dump_info(), "Can't close wifi"
