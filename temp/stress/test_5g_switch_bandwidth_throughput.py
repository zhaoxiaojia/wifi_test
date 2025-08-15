# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/21 10:50
# @Author  : chao.li
# @File    : test_5g_switch_bandwidth_throughput.py


import logging
import re
import threading
import time
from src.test import multi_stress
from src.test.performance.test_wifi_rvr_rvo import get_rx_rate, get_tx_rate, iperf_on, kill_iperf

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

ssid = 'ATC_ASUS_AX88U_2G'
router_bw40= Router(band='5G', ssid=ssid, wireless_mode='11ax', channel='149', bandwidth='40 MHz',
                      authentication='Open System')
router_bw80 = Router(band='5G', ssid=ssid, wireless_mode='11ax', channel='149', bandwidth='80 MHz',
                      authentication='Open System')

lock = threading.Lock()
test_result = {}
'''
Test step
1.Set 5G bandwidth 80M, channel 149,others keep defealt
2.Connect DUT to 5G SSID and run iperf tx and rx traffic
3.Switch bandwidth in(40M,80M),and run iperf tx and rx after switch channel
4.Repeate step3 10times
5.Compared throughput value after each round of switching

Expected Result
5.Throughput should be similar in each round

'''

dut_info = pytest.dut.checkoutput('ifconfig wlan0')
dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)[0]


@pytest.mark.wifi_connect
@pytest.fixture(autouse=True, params=[router_bw40, router_bw80] * 10)
def setup_teardown(request):
    router = request.param
    logging.info(router)
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router)
    ax88uControl.router_control.driver.quit()
    time.sleep(10)
    yield


@multi_stress
def test_5g_throughtput(device):
    device_number = device.serialnumber
    with lock:
        if device_number not in test_result.keys():
            test_result[device_number] = {'rx': [], 'tx': []}
    device.checkoutput(device.CMD_WIFI_CONNECT.format(ssid, 'open', ''))
    device.wait_for_wifi_address()
    ipfoncig_info = device.checkoutput_term('ipconfig').strip()
    pc_ip = re.findall(r'IPv4 地址.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
    tx_result = get_tx_rate(pc_ip, dut_ip, device_number, router_bw40, 4, "", "", "TCP")
    with lock:
        test_result[device_number]['tx'].append(tx_result)
    rx_result = get_rx_rate(pc_ip, dut_ip, device_number, router_bw40, 4, "", "", "TCP")
    with lock:
        test_result[device_number]['rx'].append(rx_result)
    logging.info(test_result)
