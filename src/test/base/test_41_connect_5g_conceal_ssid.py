#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_41_connect_5g_conceal_ssid.py
# Time       ：2023/7/14 15:46
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试配置
1.设置路由器5G 无线网络名称为“ATC_ASUS_AX88U_5G”，隐藏SSID设置为是，无线模式设置为149，频道带宽设置为20/40/80M,信道设置为自动，授权方式为open
2.进入设备“Settings-Network & Internet-Add New network”
3.输入SSID名字：ATC_ASUS_AX88U_5G,授权方式选择None 后确定
4.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''

ssid = 'Abc123!@#5G'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='149', bandwidth='20/40/80 MHz',
                   authentication_method='Open System', hide_ssid='是')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()


@pytest.mark.wifi_connect
def test_connect_conceal_ssid():
    pytest.dut.add_network(ssid, 'None')
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"
