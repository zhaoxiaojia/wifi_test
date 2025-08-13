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
    pytest.dut.enter_wifi_activity()
    yield
    pytest.dut.kill_setting()


def test_show_all_and_less():
    pytest.dut.wait_and_tap('See all', 'text')
    pytest.dut.wait_element('Wi-Fi', 'text')
    pytest.dut.uiautomator_dump()
    assert 'Quick connect' not in pytest.dut.get_dump_info(), "Can't show all"
    count = 0
    while not pytest.dut.find_element('See fewer', 'text'):
        pytest.dut.keyevent(20)
        if count > 100:
            raise EnvironmentError("Can't find see fewer")
    pytest.dut.wait_and_tap('See fewer', 'text')
    pytest.dut.wait_element('See all', 'text')
    pytest.dut.uiautomator_dump()
    assert 'Add new network' in pytest.dut.get_dump_info(), "Can't show all"
