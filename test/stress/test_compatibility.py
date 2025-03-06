import logging
import re
import subprocess
import time
import os
import json
import pytest

from tools.pdusnmp import power_ctrl
from tools.router_tool.Router import Router
from tools.router_tool.router_performance import FPGA_CONFIG, compatibility_router

power_delay = power_ctrl()
power_ctrl = power_delay.ctrl
router = ''
ssid = {
    '2.4G': 'Aml_AP_Comp_2.4G',
    '5G': 'Aml_AP_Comp_5G'
}
ssid_6g = 'Aml_AP_Comp_6G'
passwd = '@Aml#*st271'

wifichip, interface = pytest.chip_info.split('_')
power_delay.shutdown()
time.sleep(2)


def handle_expectdata(ip, port, band, dir):
    '''

    Args:
        ip: the ip address of the pdu
        port: the port of router,value ranges from 0-8
        band: the frequency band for Wi-Fi, only can be 2.4G or 5G
        bandwidth: the bandwidth of Wi-Fi
        dir: the direction of the throughput

    Returns:

    '''
    with open(f"{os.getcwd()}/config/compatibility_router.json", 'r') as f:
        router_datas = json.load(f)
    for data in router_datas:
        if data['ip'] == ip and data['port'] == port:
            mode = data[band]['mode']
            bandwidth = data[band]['bandwidth']
            authentication = data[band]['authentication']
            with open(f"{os.getcwd()}/config/compatibility_dut.json", 'r') as f:
                dut_data = json.load(f)
                return dut_data[band][interface][FPGA_CONFIG[wifichip][band]][bandwidth][FPGA_CONFIG[wifichip]['mimo']][
                    dir]


@pytest.fixture(scope='module', autouse=True, params=power_ctrl, ids=[str(i) for i in power_ctrl])
def power_setting(request):
    ip, port = request.param
    power_delay.switch(ip, port, 1)
    time.sleep(60)
    yield [x for x in filter(lambda x: x['port'] == port and x['ip'] == ip, compatibility_router._instances)]
    power_delay.switch(ip, port, 2)


@pytest.fixture(scope='module', autouse=True, params=['2.4G', '5G'], ids=['2.4G', '5G'])
def router_setting(power_setting, request):
    if not power_setting: raise ValueError("Pls check pdu ip address and router port")
    pc_ip = pytest.host_os.dynamic_flush_network_card('enx207bd29d4dcc')
    if pc_ip is None: assert False, "Can't get pc ip address"
    pytest.dut.ip_target = '.'.join(pc_ip.split('.')[:3])
    logging.info(f'pc_ip {pc_ip}')
    router_set = power_setting[0]
    band = request.param
    expect_tx = handle_expectdata(router_set['ip'], router_set['port'], band, 'UL')
    expect_rx = handle_expectdata(router_set['ip'], router_set['port'], band, 'DL')
    router = Router(band=band, wireless_mode=router_set[band]['mode'], channel='default',
                    authentication_method=router_set[band]['authentication'],
                    bandwidth=router_set[band]['bandwidth'], ssid=ssid[band], wpa_passwd=passwd,
                    expected_rate=f'{expect_tx} {expect_rx}')
    if pytest.connect_type == 'telnet':
        pytest.dut.roku.flush_ip()
    yield router


@pytest.mark.dependency(name="scan")
def test_scan(router_setting):
    pytest.dut.push_iperf()
    result = 'PASS' if pytest.dut.wifi_scan(router_setting.ssid) else 'FAIL'
    assert result == 'PASS', f"Can't scan target ssid {router_setting.ssid}"


@pytest.mark.dependency(name="connect", depends=["scan"])
def test_connect(router_setting):
    result = 'FAIL'
    pytest.dut.forget_wifi()
    pytest.dut.connect_ssid(router_setting)
    result = 'PASS' if pytest.dut.wait_for_wifi_address()[0] else 'FAIL'
    assert result == 'PASS', "Can't conect ssid"


@pytest.mark.dependency(depends=["connect"])
@pytest.mark.wifi_connect
def test_multi_throughtput_tx(router_setting, request):
    router_info = router_setting
    rssi_num = pytest.dut.get_rssi()
    tx_result = pytest.dut.get_tx_rate(router_info, rssi_num)
    logging.info(f'tx_result {tx_result}')
    expect_data = float(router_setting.expected_rate[0])
    logging.info(f'expect_data {expect_data}')
    request.node._store['return_value'] = tx_result
    assert all(float(x) > expect_data for x in tx_result)


@pytest.mark.dependency(depends=["connect"])
@pytest.mark.wifi_connect
def test_multi_throughtput_rx(router_setting, request):
    rssi_num = pytest.dut.get_rssi()
    rx_result = pytest.dut.get_rx_rate(router_setting, rssi_num)
    logging.info(router_setting)
    logging.info(f'rx_result {rx_result}')
    expect_data = float(router_setting.expected_rate[1])
    logging.info(f'expect_data {expect_data}')
    request.node._store['return_value'] = rx_result
    assert all(float(x) > expect_data for x in rx_result)
