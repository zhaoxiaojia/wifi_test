#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_sap_single_ssid.py
# Time       ：2023/7/25 14:48
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging

import pytest

from tools.connect_tool.adb import concomitant_dut

'''
测试步骤
SSID 为单个字符

1.设置SAP SSID为单个字符"a"

可以保存成功，并能正确显示
'''


ssid = "a"

@pytest.fixture(autouse=True)
def setup_teardown():
    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()

@pytest.mark.hot_spot
def test_sap_single_chars_ssid():
    pytest.executer.open_hotspot()
    pytest.executer.set_hotspot(ssid=ssid)
    assert ssid == pytest.executer.u().d2(resourceId="android:id/summary").get_text(), "ssid can't be set currently"
    concomitant_dut.wait_ssid_cmd(ssid)

