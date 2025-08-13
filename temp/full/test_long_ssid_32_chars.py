#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/7 14:25
# @Author  : chao.li
# @Site    :
# @File    : test_long_ssid_32_chars.py
# @Software: PyCharm


from src.test import Router, connect_ssid, forget_network_cmd, kill_setting

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
SSID 为32个字符

1.设置SAP SSID为32个字符"12345678901234567890123456789012"

可以保存成功，并能正确显示
'''


ssid = "12345678901234567890123456789012"


router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='自动', bandwidth='20 MHz',
                   authentication='Open System')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    forget_network_cmd(target_ip='192.168.50.1',ssid=ssid)
    kill_setting()


def test_connect_32_chars_ssid():
    assert connect_ssid(ssid), "Can't connect"
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"