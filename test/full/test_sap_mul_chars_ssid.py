#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_sap_mul_chars_ssid.py
# Time       ：2023/7/25 13:37
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging
import re
import time

import pytest

from ADB import concomitant_dut

'''
测试步骤
SSID含有多种字符

1.进入SoftAP设置界面；
2.修改网络名称（SSID名称），输入1-32个字符，包含特殊符号、数字、英文字母，中文
3.开启SoftAP；

1.DUT可以输入并保存
'''

ssid = 'sap_热点_123'


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.executer.change_keyboard_language()
    pytest.executer.open_hotspot()
    logging.info('setup done')
    yield
    pytest.executer.reset_keyboard_language()
    pytest.executer.close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_mul_char_ssid():
    pytest.executer.wait_and_tap('Hotspot name', 'text')
    pytest.executer.u().d2(resourceId="android:id/edit").clear_text()
    pytest.executer.checkoutput(f'am broadcast -a ADB_INPUT_TEXT --es msg  {ssid}')
    pytest.executer.wait_and_tap('GO','text')
    pytest.executer.keyevent(66)
    assert ssid == pytest.executer.u().d2(resourceId="android:id/summary").get_text(), "ssid can't be set currently"
    concomitant_dut.wait_ssid_cmd(ssid)
