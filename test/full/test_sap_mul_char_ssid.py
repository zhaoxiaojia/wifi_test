#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/8 10:12
# @Author  : chao.li
# @Site    :
# @File    : test_sap_mul_char_ssid.py
# @Software: PyCharm



import logging
import re
import time

import pytest
from tools.connect_tool.adb import ADB
from test import (accompanying_dut, change_keyboard_language,
                        close_hotspot, kill_moresetting, open_hotspot,
                        reset_keyboard_language)

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
    change_keyboard_language()
    open_hotspot()
    logging.info('setup done')
    yield
    reset_keyboard_language()
    close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_mul_ssid():
    pytest.executer.wait_and_tap('Hotspot name', 'text')
    pytest.executer.u().d2(resourceId="android:id/edit").clear_text()
    time.sleep(1)
    pytest.executer.checkoutput(f'am broadcast -a ADB_INPUT_TEXT --es msg  {ssid}')
    pytest.executer.wait_and_tap('GO', 'text')
    pytest.executer.keyevent(66)
    pytest.executer.wait_element('Hotspot name', 'text')
    assert ssid == pytest.executer.u().d2(resourceId="android:id/summary").get_text(), "ssid can't be set currently"
    accompanying_dut.wait_ssid_cmd(ssid)
