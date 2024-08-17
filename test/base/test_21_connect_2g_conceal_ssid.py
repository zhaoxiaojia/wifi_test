#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_21_connect_2g_conceal_ssid.py
# Time       ：2023/7/14 10:55
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
1.设置路由器2.4G 无线网络名称为“ATC_ASUS_AX88U_2G”，隐藏SSID设置为是，无线模式设置为自动，频道带宽设置为20/40M,信道设置为自动，授权方式为open
2.进入设备“Settings-Network & Internet-Add New network”
3.输入SSID名字：ATC_ASUS_AX88U_2G,授权方式选择None
4.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''

ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20/40 MHz',
                   authentication_method='Open System', hide_ssid='是')


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd()


@pytest.mark.wifi_connect
def test_connect_conceal_ssid():
    pytest.executer.add_network(ssid, 'None')
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"
