#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/3/28 16:44
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_country_code_us.py
# @Software: PyCharm


import time

import pytest
from test import (Router, connect_ssid, find_ssid, forget_network_cmd,
                        kill_setting, wait_for_wifi_address)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.设置DUT国家码为US:iw reg set US，查询国家码：iw reg get
2.设置AP国家码为美国，DUT 搜索并连接AP
3.设置AP国家码为中国,2.4G信道12或13，DUT搜索AP

1.查看到国家码是US
2.DUT能正常扫描并连接AP
3.DUT无法扫描到信道为12或13的AP
'''

ssid = 'ATC_ASUS_AX88U_2G'
router_us = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='Open System')
router_cn = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='13', bandwidth='40 MHz',
                   authentication_method='Open System')


@pytest.fixture(autouse=True)
def setup_teardown():
    yield
    forget_network_cmd(target_ip='192.168.50.1')
    kill_setting()


def test_connect_us():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_country('美国')
    ax88uControl.change_setting(router_us)
    ax88uControl.router_control.driver.quit()
    time.sleep(10)
    pytest.dut.checkoutput(pytest.dut.SET_COUNTRY_CODE_FORMAT.format('cn'))
    # Todo @chao.li check cn code
    pytest.dut.checkoutput(pytest.dut.GET_COUNTRY_CODE)
    connect_ssid(ssid)
    assert wait_for_wifi_address(), "Connect fail"


def test_connect_cn():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_country('中国 (默认值)')
    ax88uControl.change_setting(router_us)
    ax88uControl.router_control.driver.quit()
    time.sleep(10)
    try:
        find_ssid(ssid)
    except EnvironmentError:
        ...
    else:
        assert False, "find channel 13"
