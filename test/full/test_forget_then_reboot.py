#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_forget_then_reboot.py
# Time       ：2023/7/25 8:42
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
忘记网络重启

1.Enter wifi list ，forget the current AP1  network
2.Reboot DUT.

DUT will not auto  reconnect  AP1 wifi
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='AX only', channel='36', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()

@pytest.mark.reset_dut
def test_forget_then_reboot():
    pytest.executer.connect_ssid(ssid, passwd=passwd)
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.reboot()
    pytest.executer.wait_devices()
    try:
        pytest.executer.wait_for_wifi_address()
        assert False,"Should not reconnect"
    except AssertionError:
        assert True
