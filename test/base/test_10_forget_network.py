#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_10_forget_network.py
# Time       ：2023/7/13 11:31
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import time

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

'''
测试步骤
1.进入设置-无线网络
2.选中已经连接的无线网络，选择忘记网络，确定
3.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.kill_setting()


def test_forget_wifi():
    # connect wifi
    pytest.dut.connect_ssid(ssid,passwd)
    pytest.dut.kill_setting()
    pytest.dut.find_ssid('ATC_ASUS_AX88U_2G')
    pytest.dut.wait_and_tap('Forget network', 'text')
    for _ in range(3):
        if pytest.dut.find_element('Internet connection', 'text'):
            break
        time.sleep(1)
        pytest.dut.keyevent(23)
        pytest.dut.keyevent(23)
    pytest.dut.uiautomator_dump()
    while 'Not connected' not in pytest.dut.get_dump_info():
        time.sleep(1)
        pytest.dut.uiautomator_dump()
    assert not pytest.dut.ping(hostname="192.168.50.1")
