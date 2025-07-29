#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_63_hot_spot_control.py
# Time       ：2023/7/17 13:55
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging
import re

import pytest

from src.tools.connect_tool.adb import concomitant_dut

'''
测试步骤
1.进入设置，检查热点状态
2.重复开关热点20次.
'''



@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.dut.open_hotspot()
    yield
    pytest.dut.kill_moresetting()

@pytest.mark.hot_spot
@pytest.mark.repeat(20)
def test_hotspot_control():
    pytest.dut.get_dump_info()
    ssid = re.findall(r'text="(.*?)" resource-id="android:id/summary"', pytest.dut.get_dump_info())[0]
    logging.info(f'ssid {ssid}')
    concomitant_dut.wait_ssid_cmd(ssid)
    pytest.dut.wait_and_tap('Portable HotSpot Enabled', 'text')
    concomitant_dut.wait_ssid_disapper_cmd(ssid)
    pytest.dut.wait_and_tap('Portable HotSpot Enabled', 'text')
