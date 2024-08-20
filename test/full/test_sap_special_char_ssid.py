#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/12 10:51
# @Author  : chao.li
# @Site    :
# @File    : test_sap_special_char_ssid.py
# @Software: PyCharm



import logging

import pytest
from test import (accompanying_dut, close_hotspot,
                        kill_moresetting, open_hotspot)

'''
测试步骤
密码含有特殊字符

1.设置SAP 密码为"SAP_123test_"

可以保存成功，并能正确显示
'''

ssid = 'SAP_123test_'


@pytest.fixture(autouse=True)
def setup_teardown():
    open_hotspot()
    logging.info('setup done')
    yield
    close_hotspot()

@pytest.mark.hot_spot
def test_hotspot_blank_ssid():
    pytest.dut.wait_and_tap('Hotspot name', 'text')
    pytest.dut.u().d2(resourceId="android:id/edit").clear_text()
    pytest.dut.checkoutput(f'input text $(echo "{ssid}" | sed -e "s/ /\%s/g")')
    pytest.dut.keyevent(66)
    pytest.dut.wait_element('Hotspot name', 'text')
    assert ssid == pytest.dut.u().d2(resourceId="android:id/summary").get_text(), "ssid can't be set currently"
    accompanying_dut.wait_ssid_cmd(ssid)
