# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_5g_4k_seek.py
# Time       ：2023/9/14 10:46
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

# ssid = 'ATC_ASUS_AX88U_5G'
# passwd = 'test1234'
# router_ausu = Router(band='5G', ssid=ssid, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
#                      authentication='WPA2-Personal', wpa_passwd=passwd)
#
#
# @pytest.fixture(autouse=True, scope='session')
# def setup():
#     logging.info('start setup')
#     ax88uControl = Asusax88uControl()
#     ax88uControl.change_setting(router_ausu)
#     ax88uControl.router_control.driver.quit()
#     time.sleep(3)
#     pytest.dut.connect_ssid(ssid, passwd)
#     yield
#     pytest.dut.home()
#     pytest.dut.forget_ssid(ssid)


def test_4k_playback():
    pytest.dut.playback_youtube(seek=True, seek_time=5)
