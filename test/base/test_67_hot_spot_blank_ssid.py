#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_67_hot_spot_blank_ssid.py
# Time       ：2023/7/17 16:08
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


import logging

import pytest

from ADB import concomitant_dut

'''
测试步骤
1.设置SAP SSID为"SAP测试1234"
'''

ssid = 'SAP_12 34'


@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.executer.open_hotspot()
    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_blank_ssid():
    pytest.executer.wait_and_tap('Hotspot name', 'text')
    pytest.executer.u().d2(resourceId="android:id/edit").clear_text()
    pytest.executer.checkoutput(f'input text $(echo "{ssid}" | sed -e "s/ /\%s/g")')
    pytest.executer.keyevent(66)
    pytest.executer.wait_element('Hotspot name', 'text')
    assert ssid == pytest.executer.u().d2(resourceId="android:id/summary").get_text(), "ssid can't be set currently"
    concomitant_dut.wait_ssid_cmd(ssid)
