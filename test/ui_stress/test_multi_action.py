# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_multi_action.py
# Time       ：2023/10/12 10:37
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging
import re
import time

import pytest
from tools.Asusax88uControl import Asusax88uControl
from tools.ZTEax5400Control import ZTEax5400Control
from Router import Router
from Iperf import Iperf

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

iperf = Iperf()

@pytest.fixture(autouse=True, scope='session')
def setup():
    logging.info('start setup')
    # pytest.executer.connect_ssid(ssid1, 'Home1357')
    # pytest.executer.kill_tvsetting()
    # pytest.executer.connect_ssid(ssid2, 'Qatest123')
    # pytest.executer.kill_tvsetting()
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_ausu)
    ax88uControl.router_control.driver.quit()
    # time.sleep(3)
    # pytest.executer.connect_ssid(asus_ssid_name,passwd)
    # zte5400Control = ZTEax5400Control()
    # zte5400Control.change_setting(router_zte)
    # zte5400Control.router_control.driver.quit()
    # pytest.executer.connect_ssid(zte_ssid_name, passwd)
    yield
    pytest.executer.home()
    pytest.executer.forget_ssid(ssid1)
    pytest.executer.forget_ssid(ssid1)
    if other_flag:
        pytest.executer.forget_ssid(asus_ssid_name)
        # pytest.executer.forget_ssid(zte_ssid_name)


@pytest.mark.repeat(50000)
def test_change_ap():
    # pytest.executer.root()
    # pytest.executer.remount()
    # pytest.executer.checkoutput("echo 8 > /proc/sys/kernel/printk")
    # pytest.executer.checkoutput("iw dev wlan0 vendor send 0xc3 0xc4 0x0a 0x00 0xf0 0x00 0x04 0x0f 0xfb 0xf0 0xff;iw dev wlan0 vendor send 0xc3 0xc4 0x0a 0x00 0xf0 0x00 0x08 0x00 0x04 0x0f 0x00;iw dev wlan0 vendor send 0xc3 0xc4 0x0a 0x00 0xf0 0x00 0x20 0x00 0x00 0x00 0x01;")
    pytest.executer.connect_ssid(ssid1, 'Home1357', target='10.18')
    pytest.executer.kill_tvsetting()
    pytest.executer.playback_youtube()
    pytest.executer.connect_ssid(ssid2, 'Qatest123', target='10.18')
    pytest.executer.kill_tvsetting()
    pytest.executer.playback_youtube()
    pytest.executer.connect_ssid(asus_ssid_name, 'test1234', target="192.168.50")
    pytest.executer.kill_tvsetting()
    iperf.run_iperf(type='tx')
    iperf.run_iperf(type='rx')
    # pytest.executer.reboot()
    # pytest.executer.wait_devices()
    # pytest.executer.wait_for_wifi_service()
