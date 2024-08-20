#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/9 10:06
# @Author  : chao.li
# @Site    :
# @File    : test_sap_63_numbers_passwd.py
# @Software: PyCharm


import logging

import pytest
from test import (close_hotspot, kill_moresetting, open_hotspot)

'''
测试步骤

密码长度为63位

1.设置SAP 密码为"123456789012345678901234567890123456789012345678901234567890123"

可以保存成功，并能正确显示

'''
passwd = '123456789012345678901234567890123456789012345678901234567890123'


@pytest.fixture(autouse=True)
def setup_teardown():
    open_hotspot()
    logging.info('setup done')
    yield
    close_hotspot()


@pytest.mark.hot_spot
def test_hotspot_long_ssid():
    pytest.dut.wait_and_tap('Hotspot password', 'text')
    pytest.dut.u().d2(resourceId="android:id/edit").clear_text()
    pytest.dut.checkoutput(f'input text {passwd}')
    pytest.dut.uiautomator_dump()
    assert passwd in pytest.dut.get_dump_info(), "passwd doesn't currently"
    pytest.dut.keyevent(66)
