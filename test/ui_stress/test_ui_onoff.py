# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_ui_onoff.py
# Time       ：2023/9/4 13:56
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


import logging
import time

import pytest


@pytest.fixture(autouse=True,scope='session')
def setup():
    logging.info('start setup')
    pytest.executer.enter_wifi_activity()
    yield
    pytest.executer.kill_moresetting()

@pytest.mark.repeat(100000)
def test_onoff():
    pytest.executer.wait_and_tap('Wi-Fi', 'text')
    time.sleep(5)
    pytest.executer.wait_and_tap('Wi-Fi', 'text')
    time.sleep(10)
