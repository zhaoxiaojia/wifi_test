#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/9 10:12
# @Author  : chao.li
# @Site    :
# @File    : test_sap_cn_blank_passwd.py
# @Software: PyCharm



import logging
from test import (accompanying_dut, change_keyboard_language, close_hotspot,
                  kill_moresetting, open_hotspot, reset_keyboard_language)

import pytest

'''
测试步骤
SSID中文字符

密码含有中文和空格

1.设置SAP 密码为"SAP_测试  123"

可以保存成功，并能正确显示
'''

ssid = '"SAP_测试  123"'

@pytest.fixture(autouse=True)
def setup_teardown():
    change_keyboard_language()
    open_hotspot()
    logging.info('setup done')
    yield
    reset_keyboard_language()
    close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_cn_char_ssid():
    pytest.dut.wait_and_tap('Hotspot name', 'text')
    pytest.dut.u().d2(resourceId="android:id/edit").clear_text()
    pytest.dut.checkoutput(f'am broadcast -a ADB_INPUT_TEXT --es msg  {ssid}')
    pytest.dut.wait_and_tap('GO','text')
    pytest.dut.keyevent(66)
    pytest.dut.wait_element('Hotspot name', 'text')
    assert ssid == pytest.dut.u().d2(resourceId="android:id/summary").get_text(), "ssid can't be set currently"
    accompanying_dut.wait_ssid_cmd(ssid)
