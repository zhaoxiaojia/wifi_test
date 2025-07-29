#!/usr/bin/env python 
# -*- coding: utf-8 -*- 


"""
# File       : test_change_encrpty.py
# Time       ：2023/7/11 14:55
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""
import logging
import time

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

'''
测试步骤
1.连接ssid
2.改变信道
3.播放youtube
重复1-3
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = '12345678'
router_open = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='36', bandwidth='40 MHz',
                     authentication_method='Open System')
router_wpa = Router(band='5 GHz', ssid=ssid, wireless_mode='Legacy', channel='40', bandwidth='20 MHz',
                    authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_wpa2 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='44', bandwidth='40 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()

devices_list = ['12345678901234']


@pytest.fixture(autouse=True, scope='session')
def setup():
    # ax88uControl.change_setting(router_wpa)
    # pytest.dut.connect_ssid(ssid,passwd)
    # pytest.dut.wait_for_wifi_address()
    # ax88uControl.change_setting(router_open)
    # pytest.dut.connect_ssid(ssid)
    # pytest.dut.wait_for_wifi_address()
    yield
    ax88uControl.router_control.driver.quit()
    pytest.dut.forget_network_cmd()
    pytest.dut.kill_setting()


def test_change_ap():
    for i in [router_open, router_wpa, router_wpa2] * 10000:
        ax88uControl.change_setting(i)
        time.sleep(1)
        # for j in devices_list:
        #     pytest.execyter.serialnumber = j
        if i.authentication_method == 'Open System':
            pytest.dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT_OPEN.format(ssid))
        else:
            pytest.dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
        logging.info('connect set')
        pytest.dut.wait_for_wifi_address()
