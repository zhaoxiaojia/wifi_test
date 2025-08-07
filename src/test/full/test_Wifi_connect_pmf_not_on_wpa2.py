# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/17 10:43
# @Author  : Chao.li
# @File    : test_Wifi_connect_pmf_not_on_wpa2.py
# @Project : python
# @Software: PyCharm


from src.test import (Router, connect_ssid, forget_network_cmd, kill_setting,
                      wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
PMF 非强制启用 WPA2加密

１.AP set PMF PMF非强制启用，and secutiy WPA2;
2.DUT connect ap and play online video.

连接成功
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd,protect_frame='非强制启用')



@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_connect_wpa2_pmf_not_on():
    connect_ssid(ssid, passwd)
    assert wait_for_wifi_address(), "Connect fail"


