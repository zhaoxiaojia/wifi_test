#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/19 14:07
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_connect_ssid.py
# @Software: PyCharm


import re
from src.test import (Router, connect_ssid, forget_network_cmd, kill_setting,
                      wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
连接一个AP

1.WIFI列表中点击要连接的AP
2.输入正确密码进行连接

点击“连接”选项，开始连接AP，先显示连接，然后去获得IP地址，都成功后则显示“已连接",连接上的AP排在列表第一位
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
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_cancel_input_passwd():
    connect_ssid(ssid,passwd)
    pytest.dut.wait_element('NetWork & Internet','text')
    pytest.dut.uiautomator_dump()
    assert re.findall(check_info,pytest.dut.get_dump_info(),re.S),'ssid not no the top'