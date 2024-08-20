#!/usr/bin/env python 
# -*- coding: utf-8 -*- 


"""
# File       : test_change_channel.py
# Time       ：2023/7/11 16:08
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.连接ssid
2.改变信道
3.播放youtube
重复1-3
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345678'
router_ch1 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                    authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_ch6 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='6', bandwidth='40 MHz',
                    authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_ch11 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='N only', channel='11', bandwidth='40 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()


@pytest.fixture(autouse=True, scope='session')
def setup():
    ax88uControl.change_setting(router_ch11)
    pytest.dut.connect_ssid(ssid, passwd)
    pytest.dut.wait_for_wifi_address()
    yield
    ax88uControl.router_control.driver.quit()
    pytest.dut.forget_network_ssid(ssid)
    pytest.dut.kill_setting()


def test_change_ap():
    count = 0
    for i in [router_ch1, router_ch6, router_ch11] * 1000:
        count += 1
        try:
            logging.info(f"测试第 {count} 轮 。。。")
            ax88uControl.change_setting(i)
            # pytest.dut.connect_save_ssid(ssid, passwd)
            pytest.dut.wait_for_wifi_address()
        except Exception as e:
            ...
        # playback_youtube()
        # time.sleep(60)
