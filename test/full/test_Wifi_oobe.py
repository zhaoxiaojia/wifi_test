#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/3/30 11:12
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_oobe.py
# @Software: PyCharm

import logging
import re
import time

import pytest
from test import (Router, connect_ssid, forget_network_cmd,
                        youtube, wait_for_wifi_address,
                        wait_for_wifi_service)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.开机向导界面连接网络；
2.连接网络成功后重启DUT进行配网

能正常配网。
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = '12345678'
router = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='36', bandwidth='40 MHz',
                authentication_method='WPA2-Personal', wpa_passwd=passwd)

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
    pytest.executer.subprocess_run(
        "pm disable com.google.android.tungsten.setupwraith;settings put secure user_setup_complete 1;settings put global device_provisioned 1;settings put secure tv_user_setup_complete 1")
    time.sleep(10)


def get_factory_reset():
    pytest.executer.start_activity(*pytest.executer.SETTING_ACTIVITY_TUPLE)
    pytest.executer.wait_and_tap('Device Preferences', 'text')
    pytest.executer.wait_and_tap('About', 'text')
    pytest.executer.wait_and_tap('Factory reset', 'text')
    time.sleep(1)
    pytest.executer.keyevent(20)
    pytest.executer.keyevent(20)
    pytest.executer.keyevent(23)
    time.sleep(1)
    pytest.executer.keyevent(20)
    pytest.executer.keyevent(20)
    pytest.executer.keyevent(23)
    time.sleep(5)
    assert pytest.executer.serialnumber not in pytest.executer.checkoutput_term('adb devices'), 'Factory reset fail'
    pytest.executer.wait_devices()
    logging.info('device done')


def test_check_address_after_factory_reset():
    get_factory_reset()
    wait_for_wifi_service()
    pytest.executer.root()
    pytest.executer.remount()
    pytest.executer.wait_and_tap('English (United States)','text')
    # set android phone
    pytest.executer.wait_and_tap('Skip','text')
    # find ssid
    pytest.executer.wait_and_tap('See all', 'text')
    count = 0
    for i in range(200):
        if pytest.executer.find_element(ssid, 'text'):
            break
        if i < 100:
            pytest.executer.keyevent(20)
        else:
            pytest.executer.keyevent(19)
    else:
        raise EnvironmentError("Can't find ssid")

    pytest.executer.wait_and_tap(ssid, 'text')
    if passwd != '':
        for _ in range(5):
            logging.info('try to input passwd')
            pytest.executer.u().d2(resourceId="com.android.tv.settings:id/guidedactions_item_title").clear_text()
            time.sleep(1)
            # pytest.executer.u().d2(resourceId="com.android.tv.settings:id/guidedactions_item_title").click()
            pytest.executer.checkoutput(f'input text {passwd}')
            time.sleep(1)
            pytest.executer.uiautomator_dump()
            if passwd in pytest.executer.get_dump_info():
                pytest.executer.keyevent(66)
                break
        else:
            assert passwd in pytest.executer.get_dump_info(), "passwd not currently"
    wait_for_wifi_address()
    assert pytest.executer.ping(hostname=TARGET_IP)
    pytest.executer.wait_and_tap('Sign In', 'text', times=120)
    pytest.executer.wait_element('Sign in - Google Accounts', 'text')
    pytest.executer.text('amlogictest1@gmail.com')
    pytest.executer.keyevent(66)
    pytest.executer.wait_element('Show password', 'text')
    pytest.executer.text('amltest123')
    pytest.executer.keyevent(66)
    pytest.executer.wait_and_tap('Accept', 'text', times=20)
    pytest.executer.wait_and_tap('Accept', 'text', times=20)
    pytest.executer.wait_and_tap('Continue', 'text', times=20)
    pytest.executer.wait_and_tap('No thanks', 'text', times=20)
    pytest.executer.wait_and_tap('No thanks', 'text', times=20)
    pytest.executer.wait_and_tap('No', 'text', times=20)
    for _ in range(5):
        pytest.executer.keyevent(22)
    pytest.executer.wait_element('Apps', 'text')
