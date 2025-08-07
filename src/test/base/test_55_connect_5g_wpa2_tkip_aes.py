#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_55_connect_5g_wpa2_tkip_aes.py
# Time       ：2023/7/14 17:32
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试配置
1.设置路由器5G 无线网络名称为“ATC_ASUS_AX88U_5G”，隐藏SSID设置为否，无线模式设置为自动，频道带宽设置为20/40/80M,信道设置为149，授权方式为WPA/WPA2-Personal,WPA加密选择TKIP+AES，WPA-PSK无线密码设置为Abc@$123456，受保护的管理帧设置为禁用
2.连接5G SSID
3.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='149', bandwidth='20/40/80 MHz',
                   authentication='WPA/WPA2-Personal', wpa_passwd=passwd, protect_frame='停用', wpa_encrypt='TKIP+AES')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()


@pytest.mark.wifi_connect
def test_connect_tkip_aes_ssid():
    pytest.dut.connect_ssid_via_ui(ssid, passwd)
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"