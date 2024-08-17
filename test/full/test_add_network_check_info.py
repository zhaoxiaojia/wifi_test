#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_add_network_check_info.py
# Time       ：2023/7/24 9:42
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
添加WIFI网络

Open加密方式

添加安全性选择 加密方式-开放的网络

能添加成功
'''

ssid = 'ATC_ASUS_AX88U_5G'
router_2g = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='157', bandwidth='80 MHz',
                   authentication_method='Open System')


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


def test_add_network_open():
    pytest.executer.add_network(ssid, 'None')
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"
    pytest.executer.enter_wifi_activity()
    pytest.executer.uiautomator_dump()
    assert ssid in pytest.executer.get_dump_info(), "Can't display ssid info "
