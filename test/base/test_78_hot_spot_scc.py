#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_78_hot_spot_scc.py
# Time       ：2023/7/18 10:53
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import time

import pytest

from tools.connect_tool.adb import concomitant_dut
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

'''
测试步骤
1.DUT连接5G AP
2.DUT打开SoftAP,设置为5G频段
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
    pytest.dut.close_hotspot()
    pytest.dut.forget_network_cmd("192.169.50.1")


@pytest.mark.hot_spot
def test_hotspot_scc():
    # dut connect ssid
    cmd = pytest.dut.CMD_WIFI_CONNECT.format('ATC_ASUS_AX88U_5G', 'wpa2', '12345678')
    pytest.dut.checkoutput(cmd)
    pytest.dut.wait_for_wifi_address(cmd)
    # dut playback youtube content
    pytest.dut.playback_youtube()
    pytest.dut.home()
    # dut open hotspot
    pytest.dut.open_hotspot()
    ssid = pytest.dut.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.dut.set_hotspot(type='5.0 GHz Band')
    pytest.dut.uiautomator_dump()
    if 'WPA2 PSK' in pytest.dut.get_dump_info():
        # wpa2 need passwd
        pytest.dut.wait_and_tap('Hotspot password', 'text')
        passwd = pytest.dut.u().d2(resourceId="android:id/edit").get_text()
        logging.info(passwd)
        time.sleep(1)
        pytest.dut.keyevent(4)
        pytest.dut.keyevent(4)
        cmd = pytest.dut.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd)
    else:
        # none doesn't need passwd
        cmd = pytest.dut.CMD_WIFI_CONNECT_OPEN.format(ssid)
    pytest.dut.kill_moresetting()
    logging.info(cmd)
    # accompanying connect hotspot
    concomitant_dut.checkoutput(cmd)
    ipaddress = pytest.dut.wait_for_wifi_address(cmd, accompanying=True,target="192.168")[1]
    # accompanying playback youtube content
    concomitant_dut.playback_youtube()
    concomitant_dut.home()
    assert 'freq: 5' in concomitant_dut.checkoutput(pytest.dut.IW_LINNK_COMMAND), "Doesn't conect 5g "
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    pytest.dut.forget_network_cmd(ipaddress, accompanying=True)
