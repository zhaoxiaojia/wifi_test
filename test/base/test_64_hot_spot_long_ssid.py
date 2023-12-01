#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_64_hot_spot_long_ssid.py
# Time       ：2023/7/17 14:34
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
1.设置SAP SSID为32个字符"12345678901234567890123456789012"
'''
ssid = '12345678901234567890123456789012'


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.executer.open_hotspot()
    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_long_ssid():
    pytest.executer.set_hotspot(ssid)
    concomitant_dut.wait_ssid_cmd(ssid)
