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

import pytest

from src.tools import Iperf
from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试步骤
切换ap
'''

ssid1 = 'sunshine'
ssid2 = 'galaxy'


asus_ssid_name = 'ATC_ASUS_AX88U_2G'
passwd = 'test1234'
router_ausu = Router(band='2.4 GHz', ssid=asus_ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                     authentication='WPA2-Personal', wpa_passwd=passwd)


iperf = Iperf()

@pytest.fixture(autouse=True, scope='session')
def setup():
    logging.info('start setup')
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_ausu)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.dut.home()
    pytest.dut.forget_ssid(ssid1)
    pytest.dut.forget_ssid(ssid1)
    pytest.dut.forget_ssid(asus_ssid_name)

def switch_ap():
    logging.info('switch ap')
    pytest.dut.connect_ssid_via_ui(ssid1, 'Home1357', target='10.18')
    pytest.dut.kill_setting()
    pytest.dut.connect_ssid_via_ui(ssid2, 'Qatest123', target='10.18')
    pytest.dut.kill_setting()
    pytest.dut.connect_ssid_via_ui(asus_ssid_name, 'test1234', target="192.168.50")
    pytest.dut.kill_setting()

def playback_youtube():
    logging.info('play youtube')
    pytest.dut.playback_youtube()


def run_iperf():
    print('run iperf')
    iperf.run_iperf(type='tx')
    iperf.run_iperf(type='rx')


def onoff_wifi():
    pytest.dut.close_wifi()
    pytest.dut.open_wifi()


def reconnect_wifi():
    pytest.dut.connect_ssid_via_ui(ssid1, 'Home1357', target='10.18')
    pytest.dut.forget_ssid(ssid1)

@pytest.mark.repeat(50000)
def test_change_ap():
    # pytest.dut.root()
    # pytest.dut.remount()
    # pytest.dut.checkoutput("echo 8 > /proc/sys/kernel/printk")
    # pytest.dut.checkoutput("iw dev wlan0 vendor send 0xc3 0xc4 0x0a 0x00 0xf0 0x00 0x04 0x0f 0xfb 0xf0 0xff;iw dev wlan0 vendor send 0xc3 0xc4 0x0a 0x00 0xf0 0x00 0x08 0x00 0x04 0x0f 0x00;iw dev wlan0 vendor send 0xc3 0xc4 0x0a 0x00 0xf0 0x00 0x20 0x00 0x00 0x00 0x01;")

    {1:switch_ap(),
     2:playback_youtube(),
     3:run_iperf(),
     4:onoff_wifi(),
     5:reconnect_wifi()}[random.randint(1,5)]

    # pytest.dut.reboot()
    # pytest.dut.wait_devices()
    # pytest.dut.wait_for_wifi_service()
