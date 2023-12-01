#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_14_ssid_input.py
# Time       ：2023/7/13 16:42
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
输入网络SSID
'''

ssid = "abcdefghi"


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.executer.kill_setting()
    yield
    pytest.executer.kill_setting()


def test_ssid_input():
    pytest.executer.enter_wifi_activity()
    pytest.executer.wait_and_tap('Add new network', 'text')
    pytest.executer.checkoutput(f'input text {ssid}')
    pytest.executer.uiautomator_dump()
    assert ssid in pytest.executer.get_dump_info(), "ssid can't be input"
