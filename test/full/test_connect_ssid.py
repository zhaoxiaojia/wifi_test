# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_ssid.py
# Time       ：2023/8/1 14:45
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import re

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
连接一个AP

1.WIFI列表中点击要连接的AP
2.输入正确密码进行连接

点击“连接”选项，开始连接AP,先显示连接,然后去获得IP地址,都成功后则显示“已连接",连接上的AP排在列表第一位
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='165', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)

check_info = r'content-desc="ATC_ASUS_AX88U_5G.*?\[1200,359\]\[1920,498\]">'


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')

@pytest.mark.wifi_connect
def test_cancel_input_passwd():
    pytest.executer.connect_ssid(ssid, passwd)
    pytest.executer.wait_element('NetWork & Internet', 'text')
    pytest.executer.uiautomator_dump()
    assert re.findall(check_info, pytest.executer.get_dump_info(), re.S), 'ssid not no the top'
