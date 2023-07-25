#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_5g_iperf_rx.py
# Time       ：2023/7/24 16:43
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging
import time

import pytest
from tools.Asusax88uControl import Asusax88uControl
from Router import Router
from Iperf import Iperf
'''
测试步骤
5G-RX

1.进入SoftAP设置界面；
2.开启5G SoftAP；
3.配合终端A
4.tps 测试 RX

TPS正常，无掉零
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'

router_ch6 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='36', bandwidth='40 MHz',
                    authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()
iperf = Iperf()

@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl.change_setting(router_ch6)
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
    pytest.executer.set_hotspot(type='5.0 GHz Band')
    ssid = pytest.executer.u().d2(resourceId="android:id/summary").get_text()
    logging.info(ssid)
    assert iperf.run_iperf(type='rx'),'iperf with error'
