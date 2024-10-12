#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/3/28 10:00
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_country_code_cn.py
# @Software: PyCharm


import logging
import re
import time
from test import (Router, connect_ssid, enter_wifi_activity,
                  forget_network_cmd, kill_setting, wait_for_wifi_address)

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.设置DUT国家码为CN:iw reg set CN，查询国家码：iw reg get
2.设置AP国家码为中国，DUT 搜索并连接AP

1.查看到国家码是CN
2.DUT能正常扫描并连接AP
'''

ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='Open System')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    time.sleep(10)
    yield
    forget_network_cmd(target_ip='192.168.50.1')
    kill_setting()

def test_country_code_cn():
    pytest.dut.checkoutput(pytest.dut.SET_COUNTRY_CODE_FORMAT.format('cn'))
    # Todo @chao.li check cn code
    pytest.dut.checkoutput(pytest.dut.GET_COUNTRY_CODE)
    connect_ssid(ssid)
    assert wait_for_wifi_address(), "Connect fail"
