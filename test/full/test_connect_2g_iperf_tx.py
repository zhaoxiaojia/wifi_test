#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/14 10:12
# @Author  : chao.li
# @Site    :
# @File    : test_connect_2g_iperf_tx.py
# @Software: PyCharm


import logging
import time

import pytest
from test import (Router, close_hotspot, forget_network_cmd, iperf,
                        kill_setting, open_hotspot, wait_for_wifi_address,)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
2.4G-TX

1.进入SoftAP设置界面；
2.开启2.4G SoftAP；
3.配合终端A
4.tps 测试 TX

TPS正常，无掉零
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'

router_ch6 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='36', bandwidth='40 MHz',
                    authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl.change_setting(router_ch6)
    ax88uControl.router_control.driver.quit()
    logging.info(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
    pytest.executer.checkoutput(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
    wait_for_wifi_address()
    open_hotspot()
    logging.info('setup done')
    yield
    close_hotspot()
    forget_network_cmd(target_ip='192.168.50.1')


@pytest.mark.hot_spot
def test_hotspot_2g_iperf_tx():
    ssid = pytest.executer.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.executer.wait_and_tap('AP Band', 'text')
    pytest.executer.wait_element('2.4 GHz Band', 'text')
    pytest.executer.wait_and_tap('2.4 GHz Band', 'text')
    pytest.executer.wait_element('AP Band', 'text')
    iperf.run_iperf(type='tx')
    kill_setting()
