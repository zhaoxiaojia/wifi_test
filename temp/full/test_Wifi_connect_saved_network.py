# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/19 10:36
# @Author  : Chao.li
# @File    : test_Wifi_connect_saved_network.py
# @Project : python
# @Software: PyCharm


from src.test import (connect_save_ssid, connect_ssid, forget_network_cmd,
                      kill_setting, wait_for_wifi_address)

import pytest

'''
测试配置
Connect

1.WIFI列表中存在一个Save的网络
2.点击Save的网络
3.选择Connect

DUT会进行连接
'''

ssid1 = 'sunshine'
ssid2 = 'galaxy'


@pytest.fixture(autouse=True)
def setup():
    connect_ssid(ssid1, 'Home1357')
    connect_ssid(ssid2, 'Qatest123')
    yield
    kill_setting()


def test_():
    assert connect_save_ssid(ssid1, '10.18'), "Can't connect saved network"
