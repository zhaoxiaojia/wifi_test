import logging
import re
import subprocess
import time
from test import get_testdata

import pytest

from tools.connect_tool.adb import adb
from tools.pdusnmp import power_ctrl
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

power_delay = power_ctrl()
router = ''
ssid_2g = 'Aml_AP_Comp_2.4G'
ssid_5g = 'Aml_AP_Comp_5G'
ssid_6g = 'Aml_AP_Comp_6G'
passwd = '@Aml#*st271'

router_2g = Router(band='2.4 GHz', wireless_mode='11ac', channel='1', authentication_method='Open System',
                   bandwidth='20 MHz', ssid=ssid_2g, wpa_passwd=passwd, expected_rate='10 10')

router_5g = Router(band='5 GHz', wireless_mode='11ac', channel='36', authentication_method='Open System',
                   bandwidth='20 MHz', ssid=ssid_5g, wpa_passwd=passwd, expected_rate='10 10')
test_data = [router_2g, router_5g]


@pytest.fixture(scope='session', autouse=True)
def power_shotdown():
    power_delay.shutdown()
    time.sleep(2)


@pytest.fixture(scope='module', autouse=True, params=test_data, ids=[str(i) for i in test_data])
def router_setting(power_setting, request):
    global pc_ip
    router = request.param
    pc_ip = pytest.host_os.dynamic_flush_network_card('eth0')
    if pc_ip is None: assert False, "Can't get pc ip address"
    pytest.dut.ip_target = '.'.join(pc_ip.split('.')[:3])
    logging.info(f'pc_ip {pc_ip}')
    pytest.dut.push_iperf()
    for _ in range(30):
        info = pytest.dut.checkoutput("cmd wifi start-scan;cmd wifi list-scan-results")
        logging.info(info)
        if 'Aml_AP_Comp_' in info:
            break;
        time.sleep(3)
    else:
        assert False, "Can't scan target ssid"
    pytest.dut.forget_wifi()
    pytest.dut.checkoutput(pytest.dut.get_wifi_cmd(router))
    pytest.dut.wait_for_wifi_address()
    yield router


@pytest.fixture(scope='module', autouse=True, params=power_delay.ctrl, ids=[str(i) for i in power_delay.ctrl])
def power_setting(request):
    ip, port = request.param
    power_delay.switch(ip, port, 1)
    time.sleep(60)
    yield ip, port
    power_delay.switch(ip, port, 2)


@pytest.mark.wifi_connect
def test_multi_throughtput_tx(router_setting):
    router_info = router_setting
    rssi_info = pytest.dut.checkoutput(pytest.dut.IW_LINNK_COMMAND)
    logging.info(rssi_info)
    try:
        rssi_num = int(re.findall(r'signal:\s+-?(\d+)\s+dBm', rssi_info, re.S)[0])
        freq_num = int(re.findall(r'freq:\s+(\d+)\s+', rssi_info, re.S)[0])
    except IndexError as e:
        rssi_num = -1
        freq_num = -1
    tx_result = pytest.dut.get_tx_rate(router_info, rssi_num)
    logging.info(tx_result)
    for i in tx_result:
        if i >= float(router.expected_rate[0]):
            break
    else:
        assert False, 'Rate too low'
    time.sleep(5)


@pytest.mark.wifi_connect
def test_multi_throughtput_rx(router_setting):
    router_info = router_setting
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
    rx_result = pytest.dut.get_rx_rate(router_info, rssi_num, "TCP")
    logging.info(rx_result)
    for i in rx_result:
        if i >= float(router.expected_rate[1]):
            break
    else:
        assert False, 'Rate too low'
    time.sleep(5)
