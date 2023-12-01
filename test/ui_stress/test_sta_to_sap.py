# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_sta_to_sap.py
# Time       ：2023/9/22 10:16
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import time

import pytest

from ADB import concomitant_dut
from Router import Router
from tools.Asusax88uControl import Asusax88uControl

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345678'
router = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)

hotspot_ssid = "android_sap"
hotspot_passwd = "12345678"
@pytest.fixture(autouse=True, scope='session')
def setup():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router)
    yield
    ax88uControl.router_control.driver.quit()
    pytest.executer.forget_ssid(ssid)
    pytest.executer.kill_setting()


def test_sta_sap():
    pytest.executer.connect_ssid(ssid, passwd)
    pytest.executer.wait_for_wifi_address()
    pytest.executer.close_wifi()
    pytest.executer.open_hotspot()
    pytest.executer.set_hotspot(ssid=hotspot_ssid,passwd=hotspot_passwd,encrypt="WPA2 PSK")
    concomitant_dut.checkoutput(pytest.executer.CMD_WIFI_CONNECT.format(hotspot_ssid, 'wpa2', hotspot_passwd))
    concomitant_dut.wait_for_wifi_address(target="192.168")
    pytest.executer.close_hotspot()
    concomitant_dut.forget_wifi()