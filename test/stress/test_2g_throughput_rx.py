# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/18 15:26
# @Author  : chao.li
# @File    : test_2g_throughput_rx.py


import logging
import re
import time
from test.stress import multi_stress
from test.test_rvr import get_rx_rate, get_tx_rate, iperf_on, kill_iperf

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='11ax', channel='1', bandwidth='40 MHz',
                   authentication_method='Open System')

'''
Test step
1.DUT connect a AP with 2.4G,AX only
2.DUT do RX throughput test for about 12H.

Expected Result
DUT do TX test,wifi works well ,no disconnection.

'''

pytest.dut.IPERF_TEST_TIME = 3600 * 12
pytest.dut.IPERF_WAIT_TIME = pytest.dut.IPERF_TEST_TIME + 20
dut_info = pytest.dut.checkoutput('ifconfig wlan0')
dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)[0]


@pytest.mark.wifi_connect
@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    time.sleep(10)
    yield

@multi_stress
def test_2g_throughtput_rx(device):
    device.checkoutput(device.CMD_WIFI_CONNECT.format(ssid, 'open', ''))
    device.wait_for_wifi_address()
    ipfoncig_info = device.checkoutput_term('ipconfig').strip()
    pc_ip = re.findall(r'IPv4 地址.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
    get_rx_rate(pc_ip, dut_ip, router_2g, 4, "", "", "TCP")
