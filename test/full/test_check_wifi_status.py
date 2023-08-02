# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_check_wifi_status.py
# Time       ：2023/7/31 14:50
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
WIFI默认状态检查

进入settings内wifi,检查默认状态

wifi是默认成“打开”的
'''

WIFI_ENABLE_STRING = 'Wifi is enabled'


def test_check_wifi_status():
    pytest.executer.enter_wifi_activity()
    pytest.executer.uiautomator_dump()
    assert 'Available networks' in pytest.executer.get_dump_info(), 'Wifi is not enable'
