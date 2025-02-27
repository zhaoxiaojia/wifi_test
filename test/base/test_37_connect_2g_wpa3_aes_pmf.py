#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_37_connect_2g_wpa3_aes_pmf.py
# Time       ：2023/7/14 15:33
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

'''
测试配置
1.设置路由器2.4G 无线网络名称为“ATC_ASUS_AX88U_2G”，隐藏SSID设置为否，无线模式设置为自动，频道带宽设置为20/40M,信道设置为自动，授权方式为WPA2/WPA3,WPA加密选择AES，WPA-PSK无线密码设置为Abc@$123456，受保护的管理帧设置为强制启用
2.连接2.4G SSID
3.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='自动', bandwidth='20/40 MHz',
                   authentication_method='WPA2/WPA3-Personal', wpa_passwd=passwd, wpa_encrypt='AES',protect_frame='强制启用')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()

@pytest.mark.wifi_connect
def test_connect_wpa3_aes_pmf_ssid():
    pytest.dut.connect_ssid_via_ui(ssid, passwd)
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"
