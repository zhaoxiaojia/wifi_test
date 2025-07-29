#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_68_hot_spot_special_char_ssid.py
# Time       ：2023/7/17 16:15
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging

import pytest

from src.tools.connect_tool.adb import concomitant_dut

'''
测试步骤
1.设置SAP SSID为"SAP_12345678_"
'''

ssid = 'SAP_12345678_'


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.dut.open_hotspot()
    logging.info('setup done')
    yield
    pytest.dut.close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_special_char_ssid():
    pytest.dut.set_hotspot(ssid)
    concomitant_dut.wait_ssid_cmd(ssid)
