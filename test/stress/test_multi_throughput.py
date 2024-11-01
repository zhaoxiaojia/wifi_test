# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/31 16:45
# @Author  : chao.li
# @File    : test_multi_throughput.py


import logging
import re
import time
from test.stress import multi_stress
from test.test_rvr import get_rx_rate, get_tx_rate, iperf_on, kill_iperf

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router
from tools.pdusnmp import PowerCtrl

ssid = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='11n', channel='1', bandwidth='40 MHz',
                   authentication_method='Open System', expected_rate='0 0')

ipfoncig_info = pytest.dut.checkoutput_term('ipconfig').strip()
pc_ip = re.findall(r'IPv4 地址.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]


# ax88uControl = Asusax88uControl()
# ax88uControl.change_setting(router_2g)
# time.sleep(10)


@pytest.fixture(autouse=True, params=[1,2])
def setup_teardown(request):
    port = request.param
    s = PowerCtrl("192.168.50.230")
    s.survival(port)
    yield


@pytest.mark.wifi_connect
def test_multi_throughtput_tx():
    pytest.dut.wait_devices()
    # pytest.dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT.format(ssid, 'open', ''))
    pytest.dut.wait_for_wifi_address()
    pytest.dut.root()
    rssi_info = pytest.dut.checkoutput(pytest.dut.IW_LINNK_COMMAND)
    logging.info(rssi_info)
    try:
        rssi_num = int(re.findall(r'signal:\s+-?(\d+)\s+dBm', rssi_info, re.S)[0])
        freq_num = int(re.findall(r'freq:\s+(\d+)\s+', rssi_info, re.S)[0])
    except IndexError as e:
        rssi_num = -1
        freq_num = -1
    dut_info = pytest.dut.checkoutput('ifconfig wlan0')
    dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)[0]
    tx_result = get_tx_rate(pc_ip, dut_ip, pytest.dut.serialnumber, router_2g, 4, freq_num, rssi_num, "TCP")
    logging.info(tx_result)
    time.sleep(5)
@pytest.mark.wifi_connect
def test_multi_throughtput_rx():
    pytest.dut.wait_devices()
    # pytest.dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT.format(ssid, 'open', ''))
    pytest.dut.wait_for_wifi_address()
    pytest.dut.root()
    rssi_info = pytest.dut.checkoutput(pytest.dut.IW_LINNK_COMMAND)
    logging.info(rssi_info)
    try:
        rssi_num = int(re.findall(r'signal:\s+-?(\d+)\s+dBm', rssi_info, re.S)[0])
        freq_num = int(re.findall(r'freq:\s+(\d+)\s+', rssi_info, re.S)[0])
    except IndexError as e:
        rssi_num = -1
        freq_num = -1
    dut_info = pytest.dut.checkoutput('ifconfig wlan0')
    dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)[0]
    rx_result = get_rx_rate(pc_ip, dut_ip, pytest.dut.serialnumber, router_2g, 4, freq_num, rssi_num, "TCP")
    logging.info(rx_result)
    time.sleep(5)
