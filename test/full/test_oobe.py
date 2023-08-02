# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_oobe.py
# Time       ：2023/8/2 9:33
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import re
import time

import pytest

from tools.Asusax88uControl import Asusax88uControl
from Router import Router


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

@pytest.mark.reset_dut
def test_check_address_after_factory_reset():
    pytest.executer.get_factory_reset()
    pytest.executer.wait_for_wifi_service()
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
            # wifi.u().d2(resourceId="com.android.tv.settings:id/guidedactions_item_title").click()
            pytest.executer.checkoutput(f'input text {passwd}')
            time.sleep(1)
            pytest.executer.uiautomator_dump()
            if passwd in pytest.executer.get_dump_info():
                pytest.executer.keyevent(66)
                break
        else:
            assert passwd in pytest.executer.get_dump_info(), "passwd not currently"
    pytest.executer.wait_for_wifi_address()
    assert pytest.executer.ping(hostname="192.168.50.1")
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
