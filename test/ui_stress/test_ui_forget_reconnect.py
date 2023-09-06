#!/usr/bin/env python 
# -*- coding: utf-8 -*- 


"""
# File       : test_ui_forget_reconnect.py
# Time       ：2023/7/11 15:55
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
手动 登录 youtube 账号
连接网络
播放youtube
忘记网络
'''

ssid = 'ATC_ASUS_AX88U_5G'


@pytest.fixture(autouse=True,scope='session')
def setup_teardown():
    ...
    yield
    pytest.executer.kill_tvsetting()


@pytest.mark.repeat(5000)
def test_change_ap():
    pytest.executer.connect_ssid(ssid, '12345678')
    pytest.executer.kill_tvsetting()
    pytest.executer.wait_for_address()
    pytest.executer.playback_youtube()
    pytest.executer.forget_network_ssid(ssid)
