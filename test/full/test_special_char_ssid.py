#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/7 15:48
# @Author  : chao.li
# @Site    :
# @File    : test_special_char_ssid.py
# @Software: PyCharm




import logging
import os
import time
from test import Router, connect_ssid, forget_network_cmd, kill_setting

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
SSID含有空格

1.设置SAP SSID为"SAP_12  34"

SSID输入成功
'''


ssid = "SAP_12345678_"


router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='自动', bandwidth='20 MHz',
                   authentication_method='Open System')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    forget_network_cmd(target_ip='192.168.50.1',ssid=ssid)
    kill_setting()


def test_connect_special_chars_ssid():
    assert connect_ssid(ssid), "Can't connect"
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"

