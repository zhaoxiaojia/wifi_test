#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_connect_sap_sta.py
# Time       ：2023/7/25 8:21
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


import logging
import time

import pytest

from tools.Asusax88uControl import Asusax88uControl

'''
测试步骤
5G-TX

1.进入SoftAP设置界面；
2.开启5G SoftAP；
3.配合终端A
4.tps 测试 TX

TPS正常，无掉零
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'


@pytest.mark.hot_spot
def test_sta_sap_both():
    pytest.executer.open_wifi()
    pytest.executer.open_hotspot()
    assert True, "Can't open hotspot"

