#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_11_cancel_forget_network.py
# Time       ：2023/7/13 15:48
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试步骤
1.进入设置-无线网络
2.选中已经连接的无线网络，选择忘记网络，取消
3.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345678'
router_2g = Router(band='2.4G', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.forget_network_cmd(target_ip="192.168.50.1")
    pytest.dut.kill_setting()


def test_cancel_forgetted():
    pytest.dut.connect_ssid_via_ui(ssid, passwd)
    pytest.dut.kill_setting()
    pytest.dut.find_ssid('ATC_ASUS_AX88U_2G')
    pytest.dut.wait_and_tap('Forget network', 'text')
    pytest.dut.wait_and_tap('Cancel', 'text')
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"
