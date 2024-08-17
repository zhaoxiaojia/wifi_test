# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_saved_network.py
# Time       ：2023/8/1 13:50
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

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
    pytest.executer.connect_ssid(ssid1, 'Home1357', target="10.18")
    pytest.executer.connect_ssid(ssid2, 'Qatest123', target="10.18")
    yield
    pytest.executer.kill_setting()


@pytest.mark.wifi_connect
def test_connect_save_network():
    assert pytest.executer.connect_save_ssid(ssid1, target='10.18'), "Can't connect saved network"
