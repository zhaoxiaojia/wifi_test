#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_69_hot_spot_long_passwd.py
# Time       ：2023/7/17 16:20
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging

import pytest

from ADB import concomitant_dut

'''
测试步骤
1.设置SAP 密码为"123456789012345678901234567890123456789012345678901234567890123"
'''
ssid='android_test_sap'
passwd = '123456789012345678901234567890123456789012345678901234567890123'


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.executer.open_hotspot()
    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_special_char_ssid():
    pytest.executer.set_hotspot(ssid=ssid, passwd=passwd)
    concomitant_dut.wait_ssid_cmd(ssid)
