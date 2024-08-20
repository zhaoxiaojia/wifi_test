# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_swtich_2g_to_5g.py
# Time       ：2023/9/4 14:15
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


import logging
import time

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.ZTEax5400Control import ZTEax5400Control

asus_ssid_name = 'ATC_ASUS_AX88U_2G'
zte_ssid_name = 'ZTEax5400_5G'
passwd = 'test1234'
router_ausu = Router(band='2.4 GHz', ssid=asus_ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_zte = Router(band='5 GHz', ssid=zte_ssid_name, wireless_mode='802.11 a/n/ac', channel='161',
                    bandwidth='20MHz/40MHz/80MHz',
                    authentication_method='WPA-PSK/WPA2-PSK', wpa_passwd=passwd)


@pytest.fixture(autouse=True,scope='session')
def setup():
    logging.info('start setup')
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_ausu)
    ax88uControl.router_control.driver.quit()
    time.sleep(3)
    pytest.dut.connect_ssid(asus_ssid_name,passwd)
    zte5400Control = ZTEax5400Control()
    zte5400Control.change_setting(router_zte)
    zte5400Control.router_control.driver.quit()
    pytest.dut.connect_ssid(zte_ssid_name, passwd)
    yield
    pytest.dut.home()
    pytest.dut.forget_ssid(asus_ssid_name)
    pytest.dut.forget_ssid(zte_ssid_name)

@pytest.mark.repeat(10000)
def test_2g_swtich_5g():
    pytest.dut.connect_ssid(asus_ssid_name,target="192.168.50")
    pytest.dut.connect_ssid(zte_ssid_name,target="192.168.2")