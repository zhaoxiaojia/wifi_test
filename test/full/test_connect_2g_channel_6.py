# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_2g_channel_6.py
# Time       ：2023/7/26 14:13
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
Auto mode 信道6

Connect an AP which channel is 6

Platform connect the AP successful
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='6', bandwidth='20/40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')

@pytest.mark.wifi_connect
def test_channel_6():
    assert pytest.executer.connect_ssid(ssid, passwd=passwd),"Can't connect"
