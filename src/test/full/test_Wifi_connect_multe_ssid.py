#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/3/29 17:04
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_connect_multe_ssid.py
# @Software: PyCharm


from src.test import Router, connect_ssid, forget_network_cmd, kill_setting

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
SSID is set to 10 character or number，then platform connect the AP

Platform connect the AP successful
'''


ssid_name = '0123456789'
passwd = 'test1234'
router_2g = Router(band='2.4 GHz', ssid=ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)



@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    # ax88uControl.router_control.driver.quit()
    yield
    forget_network_cmd(target_ip='192.168.50.1')
    kill_setting()


def test_connect_multi_ssid():
    assert connect_ssid(ssid_name, passwd), "Can't connect"
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"
