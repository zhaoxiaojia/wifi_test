# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/31 16:45
# @Author  : chao.li
# @File    : test_multi_throughput.py


import logging
import re
import subprocess
import time
from os import pwrite

from serial.tools.miniterm import Transform

from test.stress import multi_stress
from test.test_rvr import get_rx_rate, get_tx_rate, iperf_on, kill_iperf

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router
from tools.pdusnmp import power_ctrl
from test import get_testdata
from tools.connect_tool.adb import ADB

test_data = get_testdata()
ipfoncig_info = subprocess.check_output('ifconfig', shell=True, encoding='utf-8').strip()
pc_ip = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
power_delay = power_ctrl()

ax88uControl = Asusax88uControl()


# time.sleep(10)
@pytest.fixture(autouse=True, params=test_data)
def router_setting(request):
    router = request.param
    ax88uControl.change_setting(router)
    yield router


@pytest.fixture(autouse=True, params=power_delay.ctrl)
def power_setting(router_setting, request):
    ip, port = request.param
    power_delay.shutdown()
    time.sleep(2)
    power_delay.switch(ip, port, 1)
    time.sleep(10)
    yield
    # power_delay.switch(ip, port, 2)


def check_iperf():
    try:
        pytest.dut.checkoutput('ls /data/iperf')
    except Exception:
        logging.info('push iperf')
        pytest.dut.push('./res/iperf', '/data/iperf')
        pytest.dut.checkoutput('chmod a+x /data/iperf')


@pytest.mark.wifi_connect
def test_multi_throughtput_tx(router_setting):
    router = router_setting
    ADB.wait_power()
    pytest.dut.wait_devices()
    pytest.dut.root()
    check_iperf()
    pytest.dut.wait_for_wifi_service()
    pytest.dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT.format(router.ssid, 'open', ''))
    pytest.dut.wait_for_wifi_address()
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
    tx_result = get_tx_rate(pc_ip, dut_ip, pytest.dut.serialnumber, router, 4, freq_num, rssi_num, "TCP")
    logging.info(tx_result)
    time.sleep(5)


@pytest.mark.wifi_connect
def test_multi_throughtput_rx(router_setting):
    router = router_setting
    ADB.wait_power()
    pytest.dut.wait_devices()
    pytest.dut.root()
    check_iperf()
    pytest.dut.wait_for_wifi_service()
    pytest.dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT.format(router.ssid, 'open', ''))
    pytest.dut.wait_for_wifi_address()
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
    rx_result = get_rx_rate(pc_ip, dut_ip, pytest.dut.serialnumber, router, 4, freq_num, rssi_num, "TCP")
    logging.info(rx_result)
    time.sleep(5)
