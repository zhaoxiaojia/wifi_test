#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2022/3/9 14:25
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_Sanity_Compatibility_Openwrt.py
# @Software: PyCharm
import logging
import time

import pytest
from lib.common.system.WIFI import WifiTestApk
from lib.common.tools.OpenWrtWifi import OpenWrt

openWrt = OpenWrt()
wifi = WifiTestApk()


@pytest.fixture(scope='function', params=openWrt.TESTCASE_2G + openWrt.TESTCASE_5G, autouse=True)
def setup_and_teardown(request):
    router = request.param
    openWrt.change_router(router)
    time.sleep(15)
    yield router
    networkid = wifi.checkoutput(wifi.CMD_WIFI_LIST_NETWORK).split('\n')[-2].split()[0]
    wifi.checkoutput(wifi.CMD_WIFI_FORGET_NETWORK.format(networkid))


def test_wifi_connect_compatibility(setup_and_teardown):
    router = setup_and_teardown
    connect_command = wifi.CMD_WIFI_CONNECT.format(router.ssid,
                                                   'wpa3' if 'sae' in router.authentication else 'wpa2',
                                                   router.passwd)
    logging.info(connect_command)
    wifi.checkoutput(connect_command)
    count = 0
    while not wifi.ping():
        time.sleep(1)
        count += 1
        if count > 10:
            assert False, "connect over time"
    assert True
    logging.info(wifi.checkoutput('ifconfig wlan0'))
