#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_sap_cn_chars_ssid.py
# Time       ：2023/7/25 13:33
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging

import pytest

from tools.connect_tool.adb import concomitant_dut

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
    pytest.executer.change_keyboard_language()
    pytest.executer.open_hotspot()
    logging.info('setup done')
    yield
    pytest.executer.reset_keyboard_language()
    pytest.executer.close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_cn_char_ssid():
    pytest.executer.wait_and_tap('Hotspot name', 'text')
    pytest.executer.u().d2(resourceId="android:id/edit").clear_text()
    pytest.executer.checkoutput(f'am broadcast -a ADB_INPUT_TEXT --es msg  {ssid}')
    pytest.executer.wait_and_tap('GO','text')
    pytest.executer.keyevent(66)
    assert ssid == pytest.executer.u().d2(resourceId="android:id/summary").get_text(), "ssid can't be set currently"
    concomitant_dut.wait_ssid_cmd(ssid)
