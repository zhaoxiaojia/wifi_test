#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_31_connect_2g_wpa2_aes_no_pmf.py
# Time       ：2023/7/14 11:36
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
1.设置路由器2.4G 无线网络名称为“ATC_ASUS_AX88U_2G”，隐藏SSID设置为否，无线模式设置为自动，频道带宽设置为20/40M,信道设置为自动，授权方式为WPA2-Personal,WPA加密选择AES，WPA-PSK无线密码设置为Abc@123456,受保护的管理帧设置为停用
2.连接2.4G SSID
3.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='自动', bandwidth='20/40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd, protect_frame='停用', wpa_encrypt='AES')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.kill_setting()

@pytest.mark.wifi_connect
def test_connect_wpa2_aes_no_pmf_ssid():
    pytest.executer.connect_ssid(ssid,passwd), "Can't connect"
    assert pytest.executer.ping(hostname="192.168.50.1"), "Can't ping"
