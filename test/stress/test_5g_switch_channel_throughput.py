# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/18 18:52
# @Author  : chao.li
# @File    : test_5g_switch_channel_throughput.py


import logging
import re
import threading
import time
from test.stress import multi_stress
from test.test_rvr import get_rx_rate, get_tx_rate, iperf_on, kill_iperf

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

ssid = 'ATC_ASUS_AX88U_5G'
router_ch149 = Router(band='5 GHz', ssid=ssid, wireless_mode='11ax', channel='149', bandwidth='80 MHz',
                      authentication_method='Open System')
router_ch161 = Router(band='5 GHz', ssid=ssid, wireless_mode='11ax', channel='161', bandwidth='80 MHz',
                      authentication_method='Open System')

lock = threading.Lock()
test_result = {}
'''
Test step
1.Set 5G bandwidth 80M, channel 149,others keep defealt
2.Connect DUT to 5G SSID and run iperf tx and rx traffic
3.Switch channels in(149,161),and run iperf tx and rx after switch channel
4.Repeate step3 10times
5.Compared througput value of channel 149,161

Expected Result
5.After switch channel, throuhput should not have much gap for every channels

'''

dut_info = pytest.dut.checkoutput('ifconfig wlan0')
dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)[0]


@pytest.mark.wifi_connect
@pytest.fixture(autouse=True, params=[router_ch149, router_ch161] * 10)
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
    tx_result = get_tx_rate(pc_ip, dut_ip, device_number, router_ch149, 4, "", "", "TCP")
    with lock:
        test_result[device_number]['tx'].append(tx_result)
    rx_result = get_rx_rate(pc_ip, dut_ip, device_number, router_ch149, 4, "", "", "TCP")
    with lock:
        test_result[device_number]['rx'].append(rx_result)
    logging.info(test_result)
