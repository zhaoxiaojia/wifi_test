#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_51_connect_5g_52channel.py
# Time       ：2023/7/14 16:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试配置
1.设置路由器5G 无线网络名称为“ATC_ASUS_AX88U_5G”，隐藏SSID设置为否，无线模式设置为自动，频道带宽设置为出20/40/80M,信道设置为52，授权方式为open
2.路由器点击保存后等待3分钟，连接5G SSID
3.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''

ssid = 'ATC_ASUS_AX88U_5G'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='52', bandwidth='20/40/80 MHz',
                   authentication='Open System')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    # time.sleep(80)
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()


@pytest.mark.wifi_connect
def test_connect_52ch_ssid():
    pytest.dut.connect_ssid_via_ui(ssid), "Can't connect"
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"
