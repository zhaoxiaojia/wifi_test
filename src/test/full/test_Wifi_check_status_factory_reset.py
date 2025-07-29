#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/3/30 15:04
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_check_status_factory_reset.py
# @Software: PyCharm



import logging
import time
from src.test import (Router, enter_wifi_activity, get_hwaddr,
                      wait_for_wifi_address, wait_for_wifi_service, youtube)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

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
    pytest.dut.reboot()
    pytest.dut.wait_devices()
    pytest.dut.root()
    pytest.dut.remount()
    pytest.dut.subprocess_run(
        "pm disable com.google.android.tungsten.setupwraith;settings put secure user_setup_complete 1;settings put global device_provisioned 1;settings put secure tv_user_setup_complete 1")
    time.sleep(10)


def get_factory_reset():
    pytest.dut.start_activity(*pytest.dut.SETTING_ACTIVITY_TUPLE)
    pytest.dut.wait_and_tap('Device Preferences', 'text')
    pytest.dut.wait_and_tap('About', 'text')
    pytest.dut.wait_and_tap('Factory reset', 'text')
    time.sleep(1)
    pytest.dut.keyevent(20)
    pytest.dut.keyevent(20)
    pytest.dut.keyevent(23)
    time.sleep(1)
    pytest.dut.keyevent(20)
    pytest.dut.keyevent(20)
    pytest.dut.keyevent(23)
    time.sleep(5)
    assert pytest.dut.serialnumber not in pytest.dut.checkoutput_term('adb devices'), 'Factory reset fail'
    pytest.dut.wait_devices()
    logging.info('device done')


def test_check_address_after_factory_reset():
    # get hwaddr before factory reset
    hwAddr_before = get_hwaddr()
    get_factory_reset()
    wait_for_wifi_service()
    pytest.dut.root()
    pytest.dut.remount()
    # get hwaddr after factory reset
    hwAddr_after = get_hwaddr()
    assert hwAddr_after != hwAddr_before, "hw addr not the same after factory reset"
    enter_wifi_activity()
    pytest.dut.uiautomator_dump()
    assert 'Available networks' in pytest.dut.get_dump_info(),'wifi not open'
    cmd = pytest.dut.CMD_WIFI_CONNECT.format('ATC_ASUS_AX88U_5G', 'wpa2', '12345678')
    wait_for_wifi_address(cmd)
    assert pytest.dut.ping(hostname=TARGET_IP)
    # check youtube playback
    youtube.playback_youtube()
