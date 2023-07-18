#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_81_wifi_onoff.py
# Time       ：2023/7/18 11:18
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import re
import time

import pytest

from tools.Asusax88uControl import Asusax88uControl
from Router import Router

'''
测试步骤
1.设置路由器5G 无线网络名称为“ATC_ASUS_AX88U_5G”，隐藏SSID设置为否，无线模式设置为Legcy，频道带宽设置为20/40/80M,信道设置为149，授权方式为WPA3，密码为Abc1234567！
2.DUT连接5G SSID,从设备 shell里面 ping 路由器网关地址：ping 192.168.50.1
3.WIFI ON/OFF 20次。
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc1234567'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='Legacy', channel='149', bandwidth='20 MHz',
                   authentication_method='WPA3-Personal', wpa_passwd=passwd)

times = pytest.config_yaml.get_note('times_081')


@pytest.fixture(autouse=True, scope='session')
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    pytest.executer.open_wifi()
    assert pytest.executer.wait_for_wifi_address(
        pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa3', passwd)), "Can't connect"
    yield
    pytest.executer.forget_network_cmd("192.168.50.1")
    pytest.executer.kill_tvsetting()


@pytest.mark.repeat(times)
def test_onoff_stress():
    pytest.executer.open_wifi()
    assert pytest.executer.wait_for_wifi_address(), "Can't get ipaddress"
    assert pytest.executer.ping(hostname="192.168.50.1"), "Can't ping"
    pytest.executer.close_wifi()
    time.sleep(1)
    assert not pytest.executer.checkoutput(
        'ifconfig wlan0 |egrep -o "inet [^ ]*"|cut -f 2 -d :'), "Still have ipaddress"
