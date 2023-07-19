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
    pytest.executer.open_wifi()
    yield
    pytest.executer.open_wifi()


def test_close_wifi():
    pytest.executer.close_wifi()
    pytest.executer.start_activity(*pytest.executer.SETTING_ACTIVITY_TUPLE)
    pytest.executer.wait_element('Network & Internet', 'text')
    pytest.executer.wait_and_tap('Network & Internet', 'text')
    pytest.executer.uiautomator_dump()
    assert pytest.executer.WIFI_BUTTON_TAG not in pytest.executer.get_dump_info(), "Can't close wifi"
