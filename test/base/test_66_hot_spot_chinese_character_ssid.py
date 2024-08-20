#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_66_hot_spot_chinese_character_ssid.py
# Time       ：2023/7/17 15:03
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging

import pytest

from tools.connect_tool.adb import concomitant_dut

'''
测试步骤
'''
ssid = 'SAP测试1234'

@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.dut.change_keyboard_language()
    pytest.dut.open_hotspot()
    logging.info('setup done')
    yield
    pytest.dut.reset_keyboard_language()
    pytest.dut.close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_chinese_char_ssid():
    pytest.dut.wait_and_tap('Hotspot name', 'text')
    pytest.dut.u().d2(resourceId="android:id/edit").clear_text()
    pytest.dut.checkoutput(f'am broadcast -a ADB_INPUT_TEXT --es msg  {ssid}')
    pytest.dut.wait_and_tap('GO','text')
    pytest.dut.keyevent(66)
    pytest.dut.wait_element('Hotspot name', 'text')
    assert ssid == pytest.dut.u().d2(resourceId="android:id/summary").get_text(), "ssid can't be set currently"
    concomitant_dut.wait_ssid_cmd(ssid)
