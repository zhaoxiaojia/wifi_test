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
from ADB import accompanying_dut

'''
测试步骤
'''
ssid = 'SAP测试1234'

@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.executer.change_keyboard_language()
    pytest.executer.open_hotspot()
    logging.info('setup done')
    yield
    pytest.executer.reset_keyboard_language()
    pytest.executer.close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_chinese_char_ssid():
    pytest.executer.wait_and_tap('Hotspot name', 'text')
    pytest.executer.u().d2(resourceId="android:id/edit").clear_text()
    pytest.executer.checkoutput(f'am broadcast -a ADB_INPUT_TEXT --es msg  {ssid}')
    pytest.executer.wait_and_tap('GO','text')
    pytest.executer.keyevent(66)
    pytest.executer.wait_element('Hotspot name', 'text')
    assert ssid == pytest.executer.u().d2(resourceId="android:id/summary").get_text(), "ssid can't be set currently"
    accompanying_dut.accompanying_dut_wait_ssid(ssid)
