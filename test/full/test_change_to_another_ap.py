# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_change_to_another_ap.py
# Time       ：2023/7/26 11:10
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import re
import time

import pytest

from Router import Router
from tools.Asusax88uControl import Asusax88uControl
from tools.ZTEax5400Control import ZTEax5400Control

'''
测试步骤
1.连接AP1
2.连接另外一个AP2

输入正确的密码后开始连接,平台能自动断开与AP1的连接,而连接上AP2.
'''

asus_ssid_name = 'ATC_ASUS_AX88U'
zte_ssid_name = 'ZTEax5400_5G'
passwd = 'test1234'
router_ausu = Router(band='2.4 GHz', ssid=asus_ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_zte = Router(band='5 GHz', ssid=zte_ssid_name, wireless_mode='802.11 a/n/ac', channel='161',
                    bandwidth='20MHz/40MHz/80MHz',
                    authentication_method='WPA-PSK/WPA2-PSK', wpa_passwd=passwd)

check_top_info = r'content-desc="ZTEax5400_5G.*?\[\d+,\d+\]\[\d+,\d+\]">'
check_save_info = 'content-desc="ATC_ASUS_AX88U,Saved'


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_ausu)
    ax88uControl.router_control.driver.quit()
    time.sleep(3)
    zte5400Control = ZTEax5400Control()
    zte5400Control.change_setting(router_zte)
    zte5400Control.router_control.driver.quit()
    yield
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')
    pytest.executer.forget_network_cmd(target_ip='192.168.2.1')
    pytest.executer.kill_setting()


@pytest.mark.wifi_connect
@pytest.mark.mul_router
def test_change_ap():
    pytest.executer.connect_ssid(asus_ssid_name, passwd)
    pytest.executer.kill_setting()
    pytest.executer.connect_ssid(zte_ssid_name, passwd)
    pytest.executer.wait_element('NetWork & Internet', 'text')
    assert zte_ssid_name in pytest.executer.checkoutput(pytest.executer.CMD_WIFI_STATUS),'Connect ssid not saved'