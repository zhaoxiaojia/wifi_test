#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_70_hot_spot_blank_passwd.py
# Time       ：2023/7/17 16:25
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

'''
测试步骤
1.设置SAP 密码为"SAP_测试  123"
'''
passwd = 'SAP_测试 123'


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.dut.change_keyboard_language()
    pytest.dut.open_hotspot()
    yield
    pytest.dut.close_hotspot()
    pytest.dut.reset_keyboard_language()



@pytest.mark.hot_spot
def test_hotspot_blank_passwd():
    pytest.dut.wait_and_tap('Hotspot password', 'text')
    pytest.dut.wait_element("android:id/edit", "resource-id")
    pytest.dut.u().d2(resourceId="android:id/edit").clear_text()
    pytest.dut.checkoutput(f'am broadcast -a ADB_INPUT_TEXT --es msg "{passwd}"')
    pytest.dut.uiautomator_dump()
    assert passwd in pytest.dut.get_dump_info(), "passwd doesn't currently"
    pytest.dut.wait_and_tap('GO', 'text')

