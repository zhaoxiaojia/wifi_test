#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_2g_iperf_tx.py
# Time       ：2023/7/24 15:53
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging

import pytest

from tools.Iperf import Iperf
from tools.router_tool.Router import Router
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

router = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20 MHz',
                    authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()
iperf = Iperf()


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl.change_setting(router)
    ax88uControl.router_control.driver.quit()
    logging.info(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
    pytest.executer.checkoutput(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
    pytest.executer.wait_for_wifi_address()
    logging.info('setup done')
    yield
    pytest.executer.close_hotspot()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


@pytest.mark.hot_spot
def test_hotspot_2g_iperf_tx():
    pytest.executer.open_hotspot()
    pytest.executer.set_hotspot(type='2.4 GHz Band')
    ssid = pytest.executer.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    assert iperf.run_iperf(type='tx'),'iperf with error'
