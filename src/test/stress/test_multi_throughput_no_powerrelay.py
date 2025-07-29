import logging
import re
import subprocess
import time
from src.test import get_testdata
from src.test.stress import device_list
from src.test.performance.test_wifi_rvr_rvo import get_rx_rate, get_tx_rate, iperf_on, kill_iperf

import pytest

from src.tools.connect_tool.adb import adb
from src.tools.pdusnmp import power_ctrl
from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

test_data = get_testdata()
ipfoncig_info = subprocess.check_output('ifconfig', shell=True, encoding='utf-8').strip()
pc_ip = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
power_delay = power_ctrl()

ax88uControl = Asusax88uControl()
router = ''


# time.sleep(10)
@pytest.fixture(scope='module', autouse=True, params=test_data, ids=[str(i) for i in test_data])
def router_setting(request):
    global router
    router = request.param
    ax88uControl.change_setting(router)
    yield


@pytest.fixture(scope='module', autouse=True, params=[adb(serialnumber=i) for i in device_list])
def device_setting(router_setting, request):
    device = request.param
    yield device


def check_iperf(device):
    device.push('./res/iperf', '/system/bin/iperf')
    device.checkoutput('chmod a+x /system/bin/iperf')


def handle_wifi_cmd(router_info, device):
    type = 'wpa3' if 'WPA3' in router_info.authentication_method else 'wpa2'
    if router_info.authentication_method.lower() in \
            ['open', '不加密', '无', 'open system', '无加密(允许所有人连接)', 'none']:
        cmd = device.CMD_WIFI_CONNECT.format(router_info.ssid, "open", "")
    else:
        cmd = device.CMD_WIFI_CONNECT.format(router_info.ssid, type,
                                             router_info.wpa_passwd)
    if router_info.hide_ssid == '是':
        cmd += device.CMD_WIFI_HIDE
    return cmd


def test_multi_throughtput_tx(device_setting):
    device = device_setting
    adb.wait_power()
    device.wait_devices()
    check_iperf(device)
    device.wait_for_wifi_service()
    time.sleep(5)
    device.forget_wifi()
    device.checkoutput(handle_wifi_cmd(router, device))
    device.wait_for_wifi_address()
    rssi_info = device.checkoutput(device.IW_LINNK_COMMAND)
    logging.info(rssi_info)
    try:
        rssi_num = int(re.findall(r'signal:\s+-?(\d+)\s+dBm', rssi_info, re.S)[0])
        freq_num = int(re.findall(r'freq:\s+(\d+)\s+', rssi_info, re.S)[0])
    except IndexError as e:
        rssi_num = -1
        freq_num = -1
    dut_info = device.checkoutput('ifconfig wlan0')
    dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)[0]
    tx_result = get_tx_rate(pc_ip, dut_ip, device.serialnumber, router, 4, freq_num, rssi_num, "TCP")
    logging.info(tx_result)
    for i in tx_result:
        if i >= float(router.expected_rate.split()[0]):
            break
    else:
        assert False, 'Rate too low'
    time.sleep(5)


def test_multi_throughtput_rx(device_setting):
    device = device_setting
    adb.wait_power()
    device.wait_devices()
    check_iperf(device)
    device.wait_for_wifi_service()
    time.sleep(5)
    device.forget_wifi()
    device.checkoutput(handle_wifi_cmd(router, device))
    device.wait_for_wifi_address()
    rssi_info = device.checkoutput(device.IW_LINNK_COMMAND)
    logging.info(rssi_info)
    try:
        rssi_num = int(re.findall(r'signal:\s+-?(\d+)\s+dBm', rssi_info, re.S)[0])
        freq_num = int(re.findall(r'freq:\s+(\d+)\s+', rssi_info, re.S)[0])
    except IndexError as e:
        rssi_num = -1
        freq_num = -1
    dut_info = device.checkoutput('ifconfig wlan0')
    dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)[0]
    rx_result = get_rx_rate(pc_ip, dut_ip, device.serialnumber, router, 4, freq_num, rssi_num, "TCP")
    logging.info(rx_result)
    for i in rx_result:
        if i >= float(router.expected_rate.split()[1]):
            break
    else:
        assert False, 'Rate too low'
    time.sleep(5)
