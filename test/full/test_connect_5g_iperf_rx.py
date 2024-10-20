#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/16 15:56
# @Author  : chao.li
# @Site    :
# @File    : test_connect_5g_iperf_rx.py
# @Software: PyCharm



import logging
import time
from test import (Router, close_hotspot, forget_network_cmd, iperf,
                  kill_setting, open_hotspot, wait_for_wifi_address)

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
5G-TX

1.进入SoftAP设置界面；
2.开启5G SoftAP；
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
    logging.info(pytest.dut.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
    pytest.dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
    wait_for_wifi_address()
    open_hotspot()
    logging.info('setup done')
    yield
    close_hotspot()
    forget_network_cmd(target_ip='192.168.50.1')


@pytest.mark.hot_spot
def test_hotspot_2g_iperf_tx():
    ssid = pytest.dut.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    pytest.dut.wait_and_tap('AP Band', 'text')
    pytest.dut.wait_element('5.0 GHz Band', 'text')
    pytest.dut.wait_and_tap('5.0 GHz Band', 'text')
    pytest.dut.wait_element('AP Band', 'text')
    iperf.run_iperf(type='rx')
    kill_setting()
