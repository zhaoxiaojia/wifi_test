#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_sap_63_chars_passwd.py
# Time       ：2023/7/25 10:02
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging

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

    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()


@pytest.mark.hot_spot
def test_hotspot_long_ssid():
    pytest.executer.open_hotspot()
    pytest.executer.set_hotspot(passwd=passwd)
    assert f'wpa_passphrase={passwd}' in pytest.executer.get_hotspot_config(), "passwd doesn't currently"

