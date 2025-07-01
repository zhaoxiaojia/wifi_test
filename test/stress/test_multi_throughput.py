# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/31 16:45
# @Author  : chao.li
# @File    : test_multi_throughput.py


import logging
import re
import subprocess
import time
from test import get_testdata
from test.test_wifi_rvr_rvo import get_rx_rate, get_tx_rate, iperf_on, kill_iperf

import pytest

from tools.connect_tool.adb import adb
from tools.pdusnmp import power_ctrl
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

test_data = get_testdata()
ipfoncig_info = subprocess.check_output('ifconfig', shell=True, encoding='utf-8').strip()
pc_ip = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
power_delay = power_ctrl()

ax88uControl = Asusax88uControl()


# time.sleep(10)
@pytest.fixture(scope='module', autouse=True, params=test_data,ids=[str(i) for i in test_data])
def router_setting(request):
    router = request.param
    ax88uControl.change_setting(router)
    yield router


@pytest.fixture(scope='module', autouse=True, params=power_delay.ctrl,ids=[str(i) for i in power_delay.ctrl])
def power_setting(router_setting, request):
    ip, port = request.param
    power_delay.shutdown()
    time.sleep(2)
    power_delay.switch(ip, port, 1)
    time.sleep(10)
    yield
    power_delay.switch(ip, port, 2)


def check_iperf():
    pytest.dut.root()
    pytest.dut.remount()
    pytest.dut.push('./res/iperf', '/system/bin/iperf')
    pytest.dut.checkoutput('chmod a+x /system/bin/iperf')


def handle_wifi_cmd(router_info):
    type = 'wpa3' if 'WPA3' in router_info.authentication_method else 'wpa2'
    if router_info.authentication_method.lower() in \
            ['open', '不加密', '无', 'open system', '无加密(允许所有人连接)', 'none']:
        cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, "open", "")
    else:
        cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, type,
                                                 router_info.wpa_passwd)
    if router_info.hide_ssid == '是':
        cmd += pytest.dut.CMD_WIFI_HIDE
    return cmd


@pytest.mark.wifi_connect
def test_multi_throughtput_tx(router_setting):
    router = router_setting
    adb.wait_power()
    pytest.dut.wait_devices()
    check_iperf()
    pytest.dut.wait_for_wifi_service()
    time.sleep(5)
    pytest.dut.forget_wifi()
    pytest.dut.checkoutput(handle_wifi_cmd(router))
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
    for i in tx_result:
        if i >= float(router.expected_rate.split()[0]):
            break
    else:
        assert False,'Rate too low'
    time.sleep(5)


@pytest.mark.wifi_connect
def test_multi_throughtput_rx(router_setting):
    router = router_setting
    adb.wait_power()
    pytest.dut.wait_devices()
    check_iperf()
    pytest.dut.wait_for_wifi_service()
    time.sleep(5)
    pytest.dut.forget_wifi()
    pytest.dut.checkoutput(handle_wifi_cmd(router))
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
    for i in rx_result:
        if i >= float(router.expected_rate.split()[1]):
            break
    else:
        assert False,'Rate too low'
    time.sleep(5)
