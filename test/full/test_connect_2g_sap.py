#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_connect_2g_sap.py
# Time       ：2023/7/24 16:58
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging
import time

import pytest

from tools.Asusax88uControl import Asusax88uControl
from Router import Router
from ADB import accompanying_dut
'''
测试步骤
1.DUT 有线连接外网；
2.配合终端：手机

配置softap 2.4G 热点，配合终端连接

能连接正常，播放视频正常
'''

router_2g = Router(band='2.4 GHz', ssid='ATC_ASUS_AX88U_2G', wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd='12345678')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    cmd = pytest.executer.CMD_WIFI_CONNECT.format('ATC_ASUS_AX88U_2G', 'wpa2', '12345678')
    logging.info(cmd)
    pytest.executer.checkoutput(cmd)
    pytest.executer.wait_for_wifi_address(cmd)
    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()
    pytest.executer.forget_network_cmd()


@pytest.mark.hot_spot
def test_hotspot_2g():
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
    logging.info(cmd)
    accompanying_dut.checkoutput(cmd)
    ipaddress = pytest.executer.wait_for_wifi_address(cmd, accompanying=True)[1]
    logging.info(accompanying_dut.checkoutput(pytest.executer.IW_LINNK_COMMAND))
    assert 'freq: 2' in accompanying_dut.checkoutput(pytest.executer.IW_LINNK_COMMAND), "Doesn't conect 2g "
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    pytest.executer.forget_network_cmd(ipaddress, accompanying=True)
