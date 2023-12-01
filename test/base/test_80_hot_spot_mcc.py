#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_80_hot_spot_mcc.py
# Time       ：2023/7/18 11:06
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging
import time

import pytest

from ADB import concomitant_dut
from Router import Router
from tools.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.DUT连接5G AP
2.DUT打开SoftAP,设置为2.4G频段
3.DUT播放在线视频
4.手机通过softap连接DUT上网后播放在线视频。
'''
router_5g = Router(band='5 GHz', ssid='ATC_ASUS_AX88U_5G', wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd='12345678')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()
    pytest.executer.forget_network_cmd("192.169.50.1")


@pytest.mark.hot_spot
def test_hotspot_scc():
    # dut connect ssid
    cmd = pytest.executer.CMD_WIFI_CONNECT.format('ATC_ASUS_AX88U_5G', 'wpa2', '12345678')
    logging.info(cmd)
    pytest.executer.wait_for_wifi_address(cmd)
    # dut playback youtube content
    pytest.executer.playback_youtube()
    pytest.executer.home()
    # dut open hotspot
    pytest.executer.open_hotspot()
    ssid = pytest.executer.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.executer.set_hotspot(type='2.4 GHz Band')
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
    concomitant_dut.checkoutput(cmd)
    ipaddress = pytest.executer.wait_for_wifi_address(cmd, accompanying=True,target="192.168")[1]
    # accompanying playback youtube content
    concomitant_dut.playback_youtube()
    concomitant_dut.home()
    assert 'freq: 2' in concomitant_dut.checkoutput(pytest.executer.IW_LINNK_COMMAND), "Doesn't conect 2g "
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    pytest.executer.forget_network_cmd(ipaddress, accompanying=True)
