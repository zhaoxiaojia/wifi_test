# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/25 15:46
# @Author  : chao.li
# @File    : test_demo.py

import itertools
import logging
import time

import pytest

bt_device = 'JBL GO 2'


def test():
    pytest.dut.start_activity(*('com.android.tv.settings', '.MainSettings'))
    for _ in range(10):
        pytest.dut.keyevent(20)
        pytest.dut.uiautomator_dump()
        if 'Pair accessory' in pytest.dut.get_dump_info():
            pytest.dut.keyevent(23)
            time.sleep(1)
            break
    else:
        assert False, "Can't find Remotes & Accessories"
    for _ in range(10):
        pytest.dut.keyevent(20)
        pytest.dut.uiautomator_dump()
        if f'text="{bt_device}" resource-id="com.android.tv.settings:id/decor_title"' in pytest.dut.get_dump_info():
            pytest.dut.keyevent(22)
            time.sleep(1)
            break
    else:
        assert False, "Can't find target bt device"
    pytest.dut.keyevent(20)
    pytest.dut.keyevent(23)
    pytest.dut.keyevent(19)
    pytest.dut.keyevent(23)