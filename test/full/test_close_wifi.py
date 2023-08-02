# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_close_wifi.py
# Time       ：2023/7/31 14:52
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
关闭WiFi

手动关闭wifi

关闭wifi后，无法搜索到AP
'''


@pytest.fixture(autouse=True)
def setup_teardown():
    yield
    pytest.executer.open_wifi()


def test_close_wifi():
    pytest.executer.close_wifi()
    pytest.executer.app_stop(pytest.executer.SETTING_ACTIVITY_TUPLE[0])
    logging.info('Enter wifi activity')
    pytest.executer.start_activity(*pytest.executer.SETTING_ACTIVITY_TUPLE)
    pytest.executer.wait_element('Network & Internet', 'text')
    pytest.executer.wait_and_tap('Network & Internet', 'text')
    pytest.executer.uiautomator_dump()
    assert pytest.executer.WIFI_BUTTON_TAG not in pytest.executer.get_dump_info(), "Can't close wifi"
