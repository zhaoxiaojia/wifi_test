#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/12 11:09
# @Author  : chao.li
# @Site    :
# @File    : test_connect_sap_5g.py
# @Software: PyCharm



import logging
import time

import pytest
from test import (Router, accompanying_dut,close_hotspot, forget_network_cmd, kill_moresetting,
                        open_hotspot, youtube, wait_for_wifi_address)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.DUT 有线连接外网；
2.配合终端：手机

配置softap 5G 热点，配合终端连接

能连接正常，播放视频正常
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
    close_hotspot()
    forget_network_cmd("192.169.50.1")


@pytest.mark.hot_spot
def test_hotspot_scc():
    # dut connect ssid
    cmd = pytest.dut.CMD_WIFI_CONNECT.format('ATC_ASUS_AX88U_5G', 'wpa2', '12345678')
    pytest.dut.checkoutput(cmd)
    wait_for_wifi_address(cmd)
    # dut open hotspot
    open_hotspot()
    ssid = pytest.dut.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.dut.wait_and_tap('AP Band', 'text')
    pytest.dut.wait_element('5.0 GHz Band', 'text')
    pytest.dut.wait_and_tap('5.0 GHz Band', 'text')
    pytest.dut.wait_element('AP Band', 'text')
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
    kill_moresetting()
    logging.info(cmd)
    # accompanying connect hotspot
    accompanying_dut.checkoutput(cmd)
    ipaddress = wait_for_wifi_address(cmd, accompanying=True)[1]
    # accompanying playback youtube content
    youtube.playback_youtube()
    time.sleep(30)
    accompanying_dut.wait_and_tap('amlogictest1@gmail.com', 'text')
    # assert youtube.check_playback_status(), 'playback status with error'
    accompanying_dut.home()
    assert 'freq: 5' in accompanying_dut.checkoutput(pytest.dut.IW_LINNK_COMMAND), "Doesn't conect 5g "
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    forget_network_cmd(ipaddress, accompanying=True)
