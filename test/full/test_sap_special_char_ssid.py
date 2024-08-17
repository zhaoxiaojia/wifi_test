#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_sap_special_char_ssid.py
# Time       ：2023/7/25 14:53
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging

import pytest

from tools.connect_tool.adb import concomitant_dut

'''
测试步骤
SSID含有空格

1.设置SAP SSID为"SAP_12  34"

SSID输入成功
'''


ssid = "SAP_12 34"


@pytest.fixture(autouse=True)
def setup_teardown():
    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()

@pytest.mark.hot_spot
def test_sap_special_chars_ssid():
    pytest.executer.open_hotspot()
    pytest.executer.set_hotspot(ssid=ssid)
    assert ssid == pytest.executer.u().d2(resourceId="android:id/summary").get_text(), "ssid can't be set currently"
    concomitant_dut.wait_ssid_cmd(ssid)
