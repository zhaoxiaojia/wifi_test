# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/16 10:29
# @Author  : Chao.li
# @File    : test_Wifi_connect_sharekey_wep_64bit_ascii.py
# @Project : python
# @Software: PyCharm


from src.test import (Router, connect_ssid, forget_network_cmd, kill_setting,
                      wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
ShareKey WEP 64bit ASCII

Connect an AP which authentication method is WEP &Certification Type:ShareKey  & 64bit &ASCII

Platform connect the AP successful
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='Legacy', channel='1', bandwidth='20 MHz',
                   authentication='Shared Key', wep_passwd=passwd,wep_encrypt='WEP-64bits')



@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_connect_wep64():
    connect_ssid(ssid, passwd)
    assert wait_for_wifi_address(), "Connect fail"

