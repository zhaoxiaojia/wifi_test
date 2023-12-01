# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_check_status_factory_reset.py
# Time       ：2023/7/31 14:35
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import re
import time

import pytest

from Router import Router
from tools.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.恢复出厂后检查网络连接状态信息；
2.恢复出厂后检查WiFi状态
3.恢复出厂后检查Mac地址

1.网络信息自动清除；
2.WiFi默认开
3.Mac地址不会变化。
'''

router = Router(band='5 GHz', ssid='ATC_ASUS_AX88U_5G', wireless_mode='N/AC/AX mixed', channel='36', bandwidth='40 MHz',
                authentication_method='WPA2-Personal', wpa_passwd='12345678')

TARGET_IP = "192.168.50.1"


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.reboot()
    pytest.executer.wait_devices()
    pytest.executer.root()
    pytest.executer.remount()
    pytest.executer.subprocess_run(pytest.executer.SKIP_OOBE)
    time.sleep(10)


@pytest.mark.reset_dut
def test_check_address_after_factory_reset():
    # get hwaddr before factory reset
    hwAddr_before = pytest.executer.get_wifi_hw_addr()
    pytest.executer.factory_reset_ui()
    pytest.executer.wait_for_wifi_service()
    pytest.executer.root()
    pytest.executer.remount()
    # get hwaddr after factory reset
    hwAddr_after = pytest.executer.get_wifi_hw_addr()
    assert hwAddr_after == hwAddr_before, "hw addr not the same after factory reset"
    pytest.executer.enter_wifi_activity()
    pytest.executer.uiautomator_dump()
    assert 'Available networks' in pytest.executer.get_dump_info(), 'wifi not open'
    cmd = pytest.executer.CMD_WIFI_CONNECT.format('ATC_ASUS_AX88U_5G', 'wpa2', '12345678')
    pytest.executer.wait_for_wifi_address(cmd)
    assert pytest.executer.ping(hostname=TARGET_IP)
    # check youtube playback
    pytest.executer.playback_youtube()
