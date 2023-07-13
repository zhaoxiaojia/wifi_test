#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_13_show_all_and_less.py
# Time       ：2023/7/13 16:38
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


import logging

import pytest


'''
测试步骤
1.进入设置-无线网络
2.选择"See all"
3.等待五秒钟，点击"See fewer"
'''


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.executer.enter_wifi_activity()
    yield
    pytest.executer.kill_tvsetting()


def test_show_all_and_less():
    pytest.executer.wait_and_tap('See all', 'text')
    pytest.executer.wait_element('Wi-Fi', 'text')
    pytest.executer.uiautomator_dump()
    assert 'Quick connect' not in pytest.executer.get_dump_info(), "Can't show all"
    count = 0
    while not pytest.executer.find_element('See fewer', 'text'):
        pytest.executer.keyevent(20)
        if count > 100:
            raise EnvironmentError("Can't find see fewer")
    pytest.executer.wait_and_tap('See fewer', 'text')
    pytest.executer.wait_element('See all', 'text')
    pytest.executer.wait_element('Quick connect', 'text')
    pytest.executer.uiautomator_dump()
    assert 'Quick connect' in pytest.executer.get_dump_info(), "Can't show all"
