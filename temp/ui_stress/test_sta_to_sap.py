# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_sta_to_sap.py
# Time       ：2023/9/22 10:16
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from src.tools.connect_tool.adb import concomitant_dut
from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345678'
router = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)

hotspot_ssid = "android_sap"
hotspot_passwd = "12345678"
@pytest.fixture(autouse=True, scope='session')
def setup():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router)
    yield
    ax88uControl.router_control.driver.quit()
    pytest.dut.forget_ssid(ssid)
    pytest.dut.kill_setting()


def test_sta_sap():
    pytest.dut.connect_ssid_via_ui(ssid, passwd)
    pytest.dut.wait_for_wifi_address()
    pytest.dut.close_wifi()
    pytest.dut.open_hotspot()
    pytest.dut.set_hotspot(ssid=hotspot_ssid,passwd=hotspot_passwd,encrypt="WPA2 PSK")
    concomitant_dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT.format(hotspot_ssid, 'wpa2', hotspot_passwd))
    concomitant_dut.wait_for_wifi_address(target="192.168")
    pytest.dut.close_hotspot()
    concomitant_dut.forget_wifi()