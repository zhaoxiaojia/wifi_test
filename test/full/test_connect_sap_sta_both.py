#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/16 16:02
# @Author  : chao.li
# @Site    :
# @File    : test_connect_sap_sta_both.py
# @Software: PyCharm


import logging
import time
from test import open_hotspot, open_wifi

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

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
    open_wifi()
    open_hotspot()
    assert True, "Can't open hotspot"
