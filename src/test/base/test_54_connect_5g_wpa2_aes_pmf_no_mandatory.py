#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_54_connect_5g_wpa2_aes_pmf_no_mandatory.py
# Time       ：2023/7/14 17:28
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试配置
1.设置路由器2.4G 无线网络名称为“ATC_ASUS_AX88U_5G”，隐藏SSID设置为否，无线模式设置为自动，频道带宽设置为20/40M,信道设置为149，授权方式为WPA2-Personal,WPA加密选择AES，WPA-PSK无线密码设置为Abc@$123456,受保护的管理帧设置非强制启用
2.连接2.4G SSID
3.从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='149', bandwidth='20/40/80 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd, protect_frame='非强制启用', wpa_encrypt='AES')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()



@pytest.mark.wifi_connect
def test_connect_aes_pmf_no_mandatory_ssid():
    pytest.dut.connect_ssid_via_ui(ssid, passwd)
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"

