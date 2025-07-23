# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/21 10:24
# @Author  : chao.li
# @File    : test_2g_switch_bandwidth_throughput.py


import logging
import re
import threading
import time
from test.stress import multi_stress
from test.performance.test_wifi_rvr_rvo import get_rx_rate, get_tx_rate, iperf_on, kill_iperf

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

ssid = 'ATC_ASUS_AX88U_2G'
router_bw20 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='11ax', channel='1', bandwidth='20 MHz',
                     authentication_method='Open System')
router_bw40 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='11ax', channel='1', bandwidth='40 MHz',
                     authentication_method='Open System')

lock = threading.Lock()
test_result = {}
'''
Test step
1.Set 2.4G bandwidth 40M, channel 11,others keep defealt
2.Connect DUT to 2.4G SSID and run iperf tx and rx traffic
3.Switch bandwidth in(20M,40M),and run iperf tx and rx after switch channel
4.Repeate step3 10times
5.Compared throughput value after each round of switching

Expected Result
5.Throughput should be similar in each round

'''

dut_info = pytest.dut.checkoutput('ifconfig wlan0')
dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)[0]


@pytest.mark.wifi_connect
@pytest.fixture(autouse=True, params=[router_bw20, router_bw40] * 10)
def setup_teardown(request):
    router = request.param
    logging.info(router)
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router)
    ax88uControl.router_control.driver.quit()
    time.sleep(10)
    yield


@multi_stress
def test_2g_throughtput(device):
    device_number = device.serialnumber
    with lock:
        if device_number not in test_result.keys():
            test_result[device_number] = {'rx': [], 'tx': []}
    device.checkoutput(device.CMD_WIFI_CONNECT.format(ssid, 'open', ''))
    device.wait_for_wifi_address()
    ipfoncig_info = device.checkoutput_term('ipconfig').strip()
    pc_ip = re.findall(r'IPv4 地址.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
    tx_result = get_tx_rate(pc_ip, dut_ip, device_number, router_bw20, 4, "", "", "TCP")
    with lock:
        test_result[device_number]['tx'].append(tx_result)
    rx_result = get_rx_rate(pc_ip, dut_ip, device_number, router_bw20, 4, "", "", "TCP")
    with lock:
        test_result[device_number]['rx'].append(rx_result)
    logging.info(test_result)
