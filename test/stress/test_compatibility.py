


import logging
import re
import subprocess
import time

from test.test_rvr import get_rx_rate, get_tx_rate, iperf_on, kill_iperf

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router
from tools.pdusnmp import power_ctrl
from test import get_testdata
from tools.connect_tool.adb import adb


power_delay = power_ctrl()
router = ''
pc_ip = ''
ssid_2g = 'Aml_AP_Comp_2.4G'
ssid_5g = 'Aml_AP_Comp_5G'
ssid_6g = 'Aml_AP_Comp_6G'
passwd = '@Aml#*st271'

router = Router(band='2.4 GHz',ssid=ssid_2g,wpa_passwd=passwd,expected_rate='10 10')
@pytest.fixture(scope='module', autouse=True, params=power_delay.ctrl,ids=[str(i) for i in power_delay.ctrl])
def power_setting(request):
    global pc_ip
    ip, port = request.param
    power_delay.shutdown()
    time.sleep(2)
    power_delay.switch(ip, port, 1)
    time.sleep(60)
    pc_ip = pytest.host_os.dynamic_flush_network_card('eth0')
    pytest.dut.ip_target = '.'.join(pc_ip.split('.')[:3])
    logging.info(f'pc_ip {pc_ip}')
    check_iperf()
    pytest.dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT.format(ssid_2g,'wpa2',passwd))
    pytest.dut.wait_for_wifi_address()
    yield
    # power_delay.switch(ip, port, 2)


def check_iperf():
    pytest.dut.checkoutput('ls /system/bin/iperf')
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
def test_multi_throughtput_tx():
    global pc_ip
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
        if i >= router.expected_rate[0]:
            break
    else:
        assert False,'Rate too low'
    time.sleep(5)


@pytest.mark.wifi_connect
def test_multi_throughtput_rx():
    global pc_ip
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
        if i >= router.expected_rate[1]:
            break
    else:
        assert False,'Rate too low'
    time.sleep(5)
