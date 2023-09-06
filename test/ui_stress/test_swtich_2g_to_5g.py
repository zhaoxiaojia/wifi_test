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
import pytest
import time
from tools.Asusax88uControl import Asusax88uControl
from tools.ZTEax5400Control import ZTEax5400Control
from Router import Router


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
    pytest.executer.connect_ssid(asus_ssid_name,passwd)
    zte5400Control = ZTEax5400Control()
    zte5400Control.change_setting(router_zte)
    zte5400Control.router_control.driver.quit()
    pytest.executer.connect_ssid(zte_ssid_name, passwd)
    yield
    pytest.executer.kill_moresetting()

@pytest.mark.repeat(10000)
def test_2g_swtich_5g():
    pytest.executer.connect_ssid(asus_ssid_name,target="192.168.50")
    pytest.executer.connect_ssid(zte_ssid_name,target="192.168.2")