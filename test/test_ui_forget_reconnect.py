# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_ui_forget_reconnect.py
# Time       ：2023/7/11 15:55
# Author     ：chao.li
# version    ：python 3.6
# Description：
"""



import logging
import re
import time

import pytest


'''
测试步骤
手动 登录 youtube 账号
连接网络
播放youtube
忘记网络
'''

ssid = 'sunshine'


@pytest.fixture(autouse=True)
def setup_teardown():
    ...
    yield
    pytest.executer.kill_tvsetting()


@pytest.mark.repeat(500)
def test_change_ap():
    pytest.executer.connect_ssid(ssid, 'Home1357')
    pytest.executer.kill_tvsetting()
    pytest.executer.wait_for_address()
    pytest.executer.playback_youtube()
    time.sleep(60)
    pytest.executer.forget_network_ssid(ssid)
