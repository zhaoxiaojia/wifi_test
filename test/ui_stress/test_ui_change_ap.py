#!/usr/bin/env python 
# -*- coding: utf-8 -*- 


"""
# File       : test_ui_change_ap.py
# Time       ：2023/7/10 18:37
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

'''
测试步骤
切换ap
'''

ssid1 = 'sunshine'
ssid2 = 'galaxy'

other_flag = False
try:
    asus_ssid_name = 'ATC_ASUS_AX88U_2G'
    # zte_ssid_name = 'ZTEax5400_5G'
    passwd = 'test1234'
    router_ausu = Router(band='2.4 GHz', ssid=asus_ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                         authentication_method='WPA2-Personal', wpa_passwd=passwd)
    # router_zte = Router(band='5 GHz', ssid=zte_ssid_name, wireless_mode='802.11 a/n/ac', channel='161',
    #                     bandwidth='20MHz/40MHz/80MHz',
    #                     authentication_method='WPA2-PSK/WPA3-PSK', wpa_passwd=passwd)
    other_flag = True
except Exception as e:
    other_flag = False


@pytest.fixture(autouse=True, scope='session')
def setup():
    logging.info('start setup')
    # pytest.dut.connect_ssid(ssid1, 'Home1357')
    # pytest.dut.kill_tvsetting()
    # pytest.dut.connect_ssid(ssid2, 'Qatest123')
    # pytest.dut.kill_tvsetting()
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_ausu)
    ax88uControl.router_control.driver.quit()
    # time.sleep(3)
    # pytest.dut.connect_ssid(asus_ssid_name,passwd)
    # zte5400Control = ZTEax5400Control()
    # zte5400Control.change_setting(router_zte)
    # zte5400Control.router_control.driver.quit()
    # pytest.dut.connect_ssid(zte_ssid_name, passwd)
    yield
    pytest.dut.home()
    pytest.dut.forget_ssid(ssid1)
    pytest.dut.forget_ssid(ssid1)
    if other_flag:
        pytest.dut.forget_ssid(asus_ssid_name)
        # pytest.dut.forget_ssid(zte_ssid_name)


@pytest.mark.repeat(50000)
def test_change_ap():
    pytest.dut.connect_ssid_via_ui(ssid1, 'Home1357', target='10.18')
    pytest.dut.kill_setting()
    pytest.dut.playback_youtube()
    pytest.dut.connect_ssid_via_ui(ssid2, 'Qatest123', target='10.18')
    pytest.dut.kill_setting()
    pytest.dut.playback_youtube()
    pytest.dut.connect_ssid_via_ui(asus_ssid_name, 'test1234', target="192.168.50")
    pytest.dut.kill_setting()
    pytest.dut.playback_youtube()
    #     pytest.dut.kill_tvsetting()
    #     pytest.dut.playback_youtube()
    # pytest.dut.connect_ssid(zte_ssid_name, target="192.168.2")``
    # pytest.dut.kill_tvsetting()
    # pytest.dut.playback_youtube()
