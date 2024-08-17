# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_2g_4k_seek.py
# Time       ：2023/9/14 10:04
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import time

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'test1234'
router_ausu = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(autouse=True, scope='session')
def setup():
    logging.info('start setup')
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_ausu)
    ax88uControl.router_control.driver.quit()
    time.sleep(3)
    pytest.executer.connect_ssid(ssid, passwd)
    yield
    pytest.executer.home()
    pytest.executer.forget_ssid(ssid)


def test_4k_playback():
    pytest.executer.playback_youtube(seek=True, seek_time=5)
