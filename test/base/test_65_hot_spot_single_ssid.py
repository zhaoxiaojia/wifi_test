#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_65_hot_spot_single_ssid.py
# Time       ：2023/7/17 14:53
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging

import pytest

from tools.connect_tool.adb import concomitant_dut

'''
测试步骤
1.设置SAP SSID为单个字符"a"
'''
ssid = 'a'


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.executer.open_hotspot()
    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_single_ssid():
    pytest.executer.set_hotspot(ssid)
    concomitant_dut.wait_ssid_cmd(ssid)
