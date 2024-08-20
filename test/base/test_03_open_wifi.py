#!/usr/bin/env python 
# -*- coding: utf-8 -*- 


"""
# File       : test_03_open_wifi.py
# Time       ：2023/7/12 13:59
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
2.WIFI开关为关闭状态，点击WIFI开关
'''


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.dut.close_wifi()
    yield
    pytest.dut.open_wifi()


def test_open_wifi():
    pytest.dut.open_wifi()
    pytest.dut.enter_wifi_activity()
    pytest.dut.uiautomator_dump()
    assert pytest.dut.WIFI_BUTTON_TAG in pytest.dut.get_dump_info(), "Can't open wifi"
