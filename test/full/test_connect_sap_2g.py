#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/14 09:56
# @Author  : chao.li
# @Site    :
# @File    : test_connect_sap_2g.py
# @Software: PyCharm



import logging
import time

import pytest
from test import (Router, accompanying_dut,close_hotspot, forget_network_cmd, kill_moresetting,
                        open_hotspot, wait_for_wifi_address, youtube)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.DUT 有线连接外网；
2.配合终端：手机

配置softap 2.4G 热点，配合终端连接

能连接正常，播放视频正常
'''

router_2g = Router(band='2.4 GHz', ssid='ATC_ASUS_AX88U_2G', wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='WPA/WPA2-Personal', wpa_passwd='12345678')


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    logging.info('setup done')
    yield
    close_hotspot()
    forget_network_cmd("192.169.50.1")


@pytest.mark.hot_spot
def test_hotspot_scc():
    # dut connect ssid
    cmd = pytest.executer.CMD_WIFI_CONNECT.format('ATC_ASUS_AX88U_2G', 'wpa2', '12345678')
    logging.info(cmd)
    pytest.executer.checkoutput(cmd)
    wait_for_wifi_address(cmd)
    # dut playback youtube content
    youtube.playback(youtube.PLAYERACTIVITY_REGU, youtube.VIDEO_TAG_LIST[0]['link'])
    pytest.executer.wait_and_tap('amlogictest1@gmail.com','text')
    # assert youtube.check_playback_status(), 'playback status with error'
    pytest.executer.home()
    # dut open hotspot
    open_hotspot()
    ssid = pytest.executer.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.executer.wait_and_tap('AP Band', 'text')
    pytest.executer.wait_element('2.4 GHz Band', 'text')
    pytest.executer.wait_and_tap('2.4 GHz Band', 'text')
    pytest.executer.wait_element('AP Band', 'text')
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
    kill_moresetting()
    logging.info(cmd)
    # accompanying connect hotspot
    accompanying_dut.checkoutput(cmd)
    ipaddress = wait_for_wifi_address(cmd, accompanying=True)[1]
    # accompanying playback youtube content
    youtube.serialnumber = accompanying_dut.serialnumber
    youtube.playback(youtube.PLAYERACTIVITY_REGU, youtube.VIDEO_TAG_LIST[0]['link'])
    accompanying_dut.wait_and_tap('amlogictest1@gmail.com', 'text')
    # assert youtube.check_playback_status(), 'playback status with error'
    accompanying_dut.home()
    assert 'freq: 2' in accompanying_dut.checkoutput(pytest.executer.IW_LINNK_COMMAND), "Doesn't conect 2g "
    ipaddress = '.'.join(ipaddress.split('.')[:3] + ['1'])
    forget_network_cmd(ipaddress, accompanying=True)