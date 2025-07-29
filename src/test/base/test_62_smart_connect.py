#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_62_smart_connect.py
# Time       ：2023/7/17 13:50
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试步骤
1.设置路由器SSID"ATC_ASUS_AX88U"，开启smart connect
2.DUT连接路由器 ATC_ASUS_AX88U，cmd下输入iw wlan0 link
'''

ssid = 'ATC_ASUS_AX88U'
passwd = 'test1234'
router = Router(band='2.4 GHz', ssid=ssid, wireless_mode='Legacy', channel='自动', bandwidth='20 MHz',
                authentication_method='WPA2-Personal', wpa_passwd=passwd,
                smart_connect=True)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()


@pytest.mark.wifi_connect
def test_smart_connect():
    pytest.dut.connect_ssid_via_ui(ssid, passwd), "Can't connect"
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"
    assert 'freq: 5' in pytest.dut.checkoutput(pytest.dut.IW_LINNK_COMMAND), "Doesn't conect 5g "
