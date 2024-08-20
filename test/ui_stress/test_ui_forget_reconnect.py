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

ssid = 'sunshine'
passwd = 'Home1357'

@pytest.fixture(autouse=True,scope='session')
def setup_teardown():
    ...
    yield
    pytest.dut.kill_setting()


@pytest.mark.repeat(5000)
def test_change_ap():
    pytest.dut.connect_ssid(ssid, passwd,target='10.18.32')
    pytest.dut.kill_setting()
    pytest.dut.playback_youtube()
    pytest.dut.forget_ssid(ssid)
