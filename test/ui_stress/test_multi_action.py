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
import random
import re
import time

import pytest

from Iperf import Iperf
from Router import Router
from tools.Asusax88uControl import Asusax88uControl
from tools.ZTEax5400Control import ZTEax5400Control

'''
测试步骤
切换ap
'''

ssid1 = 'sunshine'
ssid2 = 'galaxy'


asus_ssid_name = 'ATC_ASUS_AX88U_2G'
passwd = 'test1234'
router_ausu = Router(band='2.4 GHz', ssid=asus_ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)


iperf = Iperf()

@pytest.fixture(autouse=True, scope='session')
def setup():
    logging.info('start setup')
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_ausu)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.home()
    pytest.executer.forget_ssid(ssid1)
    pytest.executer.forget_ssid(ssid1)
    pytest.executer.forget_ssid(asus_ssid_name)

def switch_ap():
    logging.info('switch ap')
    pytest.executer.connect_ssid(ssid1, 'Home1357', target='10.18')
    pytest.executer.kill_setting()
    pytest.executer.connect_ssid(ssid2, 'Qatest123', target='10.18')
    pytest.executer.kill_setting()
    pytest.executer.connect_ssid(asus_ssid_name, 'test1234', target="192.168.50")
    pytest.executer.kill_setting()

def playback_youtube():
    logging.info('play youtube')
    pytest.executer.playback_youtube()


def run_iperf():
    print('run iperf')
    iperf.run_iperf(type='tx')
    iperf.run_iperf(type='rx')


def onoff_wifi():
    pytest.executer.close_wifi()
    pytest.executer.open_wifi()


def reconnect_wifi():
    pytest.executer.connect_ssid(ssid1, 'Home1357', target='10.18')
    pytest.executer.forget_ssid(ssid1)

@pytest.mark.repeat(50000)
def test_change_ap():
    # pytest.executer.root()
    # pytest.executer.remount()
    # pytest.executer.checkoutput("echo 8 > /proc/sys/kernel/printk")
    # pytest.executer.checkoutput("iw dev wlan0 vendor send 0xc3 0xc4 0x0a 0x00 0xf0 0x00 0x04 0x0f 0xfb 0xf0 0xff;iw dev wlan0 vendor send 0xc3 0xc4 0x0a 0x00 0xf0 0x00 0x08 0x00 0x04 0x0f 0x00;iw dev wlan0 vendor send 0xc3 0xc4 0x0a 0x00 0xf0 0x00 0x20 0x00 0x00 0x00 0x01;")

    {1:switch_ap(),
     2:playback_youtube(),
     3:run_iperf(),
     4:onoff_wifi(),
     5:reconnect_wifi()}[random.randint(1,5)]

    # pytest.executer.reboot()
    # pytest.executer.wait_devices()
    # pytest.executer.wait_for_wifi_service()
