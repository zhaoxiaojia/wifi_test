#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_79_hot_spot_mcc.py
# Time       ：2023/7/18 11:00
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import time

import pytest

from tools.Asusax88uControl import Asusax88uControl
from ADB import accompanying_dut
from Router import Router

'''
测试步骤
1.DUT连接2.4G AP
2.DUT打开SoftAP,设置为5G频段
3.DUT播放在线视频
4.手机通过softap连接DUT上网后播放在线视频。
'''
router_2g = Router(band='2.4 GHz', ssid='ATC_ASUS_AX88U_2G', wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd='12345678')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()
    pytest.executer.forget_network_cmd("192.169.50.1")


@pytest.mark.hot_spot
def test_hotspot_scc():
    # dut connect ssid
    cmd = pytest.executer.CMD_WIFI_CONNECT.format('ATC_ASUS_AX88U_2G', 'wpa2', '12345678')
    logging.info(cmd)
    pytest.executer.wait_for_wifi_address(cmd)
    # dut playback youtube content
    pytest.executer.playback_youtube()
    pytest.executer.wait_and_tap('amlogictest1@gmail.com', 'text')
    # assert youtube.check_playback_status(), 'playback status with error'
    pytest.executer.home()
    # dut open hotspot
    pytest.executer.open_hotspot()
    ssid = pytest.executer.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.executer.set_hotspot(type='5.0 GHz Band')
    pytest.executer.uiautomator_dump()
    if 'WPA2 PSK' in pytest.executer.get_dump_info():
        # wpa2 need passwd
        pytest.executer.wait_and_tap('Hotspot password', 'text')
        passwd = pytest.executer.u().d2(resourceId="android:id/edit").get_text()
        logging.info(passwd)
        time.sleep(1)
        pytest.executer.keyevent(4)
        pytest.executer.keyevent(4)
        cmd = pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd)
    else:
        # none doesn't need passwd
        cmd = pytest.executer.CMD_WIFI_CONNECT_OPEN.format(ssid)
    pytest.executer.kill_moresetting()
    logging.info(cmd)
    # accompanying connect hotspot
    accompanying_dut.checkoutput(cmd)
    ipaddress = pytest.executer.wait_for_wifi_address(cmd, accompanying=True)[1]
    # accompanying playback youtube content
    try:
        accompanying_dut.playback_youtube()
        # accompanying_dut.wait_and_tap('amlogictest1@gmail.com', 'text')
        # assert youtube.check_playback_status(), 'playback status with error'
        accompanying_dut.home()
    except Exception as e:
        ...
    assert 'freq: 5' in accompanying_dut.checkoutput(pytest.executer.IW_LINNK_COMMAND), "Doesn't conect 5g "
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    pytest.executer.forget_network_cmd(ipaddress, accompanying=True)
