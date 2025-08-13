#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/8 11:24
# @Author  : chao.li
# @Site    :
# @File    : test_sap_cn_char_ssid.py
# @Software: PyCharm



import logging
from src.test import (accompanying_dut, change_keyboard_language, close_hotspot,
                      kill_moresetting, open_hotspot, reset_keyboard_language)

import pytest

'''
测试步骤
SSID中文字符

1.进入SoftAP设置界面；
2.修改网络名称（SSID名称），输入1-10个中文
3.开启SoftAP；
4.添加配合终端设备

2.SSID全部中文最大输入数10，达到最大字符后保存按钮显示可以保存
4.辅助机可以正确连接该AP
'''
ssid = '这是个调皮的中文热点'

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
