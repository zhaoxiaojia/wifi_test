# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_sap_2g_to_5g.py
# Time       ：2023/9/22 14:22
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.connect_tool.adb import concomitant_dut

hotspot_ssid = "android_sap"
hotspot_passwd = "12345678"
@pytest.fixture(autouse=True, scope='session')
def setup():
    yield
    pytest.dut.kill_setting()


def test_sta_sap():
    pytest.dut.open_hotspot()
    pytest.dut.set_hotspot(ssid=hotspot_ssid,passwd=hotspot_passwd,encrypt="WPA2 PSK",type="2.4 GHz Band")
    concomitant_dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT.format(hotspot_ssid, 'wpa2', hotspot_passwd))
    concomitant_dut.wait_for_wifi_address(target="192.168")
    assert 'freq: 2' in concomitant_dut.checkoutput(pytest.dut.IW_LINNK_COMMAND), "Doesn't conect 2g "
    pytest.dut.open_hotspot()
    pytest.dut.set_hotspot(ssid=hotspot_ssid,passwd=hotspot_passwd,encrypt="WPA2 PSK",type="5.0 GHz Band")
    concomitant_dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT.format(hotspot_ssid, 'wpa2', hotspot_passwd))
    concomitant_dut.wait_for_wifi_address(target="192.168")
    assert 'freq: 5' in concomitant_dut.checkoutput(pytest.dut.IW_LINNK_COMMAND), "Doesn't conect 5g "
    pytest.dut.close_hotspot()
    concomitant_dut.forget_wifi()