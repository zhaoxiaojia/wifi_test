#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_sap_63_numbers_passwd.py
# Time       ：2023/7/25 10:24
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging

import pytest

'''
测试步骤

密码长度为63位

1.设置SAP 密码为"123456789012345678901234567890123456789012345678901234567890123"

可以保存成功，并能正确显示

'''
passwd = '123456789012345678901234567890123456789012345678901234567890123'


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