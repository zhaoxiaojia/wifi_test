#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/9 09:55
# @Author  : chao.li
# @Site    :
# @File    : test_sap_63_chars_passwd.py
# @Software: PyCharm


import logging
from test import close_hotspot, kill_moresetting, open_hotspot

import pytest

'''
测试步骤

密码63个数字英文组合

1.进入SoftAP设置界面；
2.设置任意WPA2加密的AP
3.进入密码输入界面后输入63个数字英文的组合并确认
4.添加配合终端设备

密码长度8-64，其余个数的字符，应该无法继续输入或灰化保存按纽

'''
passwd = 'abcdefghijabcdefghij1234567890123456789012345678901234567890123'


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
