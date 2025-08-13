# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/18 15:40
# @Author  : chao.li
# @File    : test_5g_ax_throughput_rx.py


import re
import time
from src.test import multi_stress
from src.test.performance.test_wifi_rvr_rvo import get_rx_rate, get_tx_rate, iperf_on, kill_iperf

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

ssid = 'ATC_ASUS_AX88U_5G'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='11ax', channel='36', bandwidth='40 MHz',
                   authentication='Open System')

'''
Test step
1.DUT connect a AP with 5G,AX only
2.DUT do RX throughput test for about 12H.

Expected Result
DUT do RX test,wifi works well ,no disconnection.

'''

pytest.dut.IPERF_TEST_TIME = 3600 * 12
pytest.dut.IPERF_WAIT_TIME = pytest.dut.IPERF_TEST_TIME + 20
dut_info = pytest.dut.checkoutput('ifconfig wlan0')
dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)[0]


@pytest.mark.wifi_connect
@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    time.sleep(10)
    yield


@multi_stress
def test_5g_throughtput_rx(device):
    device.checkoutput(device.CMD_WIFI_CONNECT.format(ssid, 'open', ''))
    device.wait_for_wifi_address()
    ipfoncig_info = device.checkoutput_term('ipconfig').strip()
    pc_ip = re.findall(r'IPv4 地址.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
    get_rx_rate(pc_ip, dut_ip, router_5g, 4, "", "", "TCP")
