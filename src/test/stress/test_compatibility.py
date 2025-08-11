#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: test_compatibility.py
@time: 2025/7/22 21:40 
@desc: 
'''

import logging
import time
import os
import json
import pytest

from src.tools.pdusnmp import power_ctrl
from src.tools.router_tool.Router import Router
from src.tools.router_tool.router_performance import compatibility_router
from src.util.constants import RouterConst

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
                return dut_data[band][interface.upper()][RouterConst.FPGA_CONFIG[wifichip][band]][bandwidth][
                    RouterConst.FPGA_CONFIG[wifichip]['mimo']][
                    dir]


@pytest.fixture(scope='module', autouse=True, params=power_ctrl, ids=[str(i) for i in power_ctrl])
def power_setting(request):
    ip, port = request.param
    power_delay.switch(ip, port, 1)
    time.sleep(60)
    try:
        info = [x for x in filter(lambda x: x['port'] == port and x['ip'] == ip, compatibility_router._instances)][0]
    except:
        info = ''
    logging.info(f'power yield {info}')
    yield info
    logging.info('test done shutdown the router')
    power_delay.switch(ip, port, 2)


@pytest.fixture(scope='module', autouse=True, params=['2.4G', '5G'], ids=['2.4G', '5G'])
def router_setting(power_setting, request):
    if not power_setting: raise ValueError("Pls check pdu ip address and router port")
    pytest.dut.pc_ip = pytest.host_os.dynamic_flush_network_card('eth1')
    if pytest.dut.pc_ip is None: assert False, "Can't get pc ip address"
    logging.info(f'pc_ip {pytest.dut.pc_ip}')
    router_set = power_setting
    band = request.param
    expect_tx = handle_expectdata(router_set['ip'], router_set['port'], band, 'UL')
    expect_rx = handle_expectdata(router_set['ip'], router_set['port'], band, 'DL')
    router = Router(ap=router_set['mode'], band=band, wireless_mode=router_set[band]['mode'],
                    channel='default', authentication=router_set[band]['authentication'],
                    bandwidth=router_set[band]['bandwidth'], ssid=ssid[band], wpa_passwd=passwd,
                    expected_rate=f'{expect_tx} {expect_rx}')
    if pytest.connect_type == 'telnet':
        pytest.dut.roku.flush_ip()
    logging.info(f'router yield {router}')
    yield router


@pytest.mark.dependency(name="scan")
def test_scan(router_setting):
    result = 'FAIL'
    if pytest.connect_type == 'telnet':
        result = 'PASS' if pytest.dut.roku.flush_ip() else 'FAIL'
        assert result == 'PASS', f"Can't be reconnected"
    pytest.dut.push_iperf()
    result = 'PASS' if pytest.dut.wifi_scan(router_setting.ssid) else 'FAIL'
    assert result == 'PASS', f"Can't scan target ssid {router_setting.ssid}"


@pytest.mark.dependency(name="connect", depends=["scan"])
def test_connect(router_setting):
    result = 'FAIL'
    pytest.dut.forget_wifi()
    pytest.dut.connect_ssid(router_setting)
    result = 'PASS' if pytest.dut.wait_for_wifi_address()[0] else 'FAIL'
    pytest.dut.get_rssi()
    if router_setting.band == '5G': assert pytest.dut.freq_num > 5000
    if router_setting.band == '2.5G': assert pytest.dut.freq_num < 5000
    router_setting = router_setting._replace(channel=pytest.dut.channel)
    assert result == 'PASS', "Can't connect ssid"


@pytest.mark.dependency(depends=["connect"])
@pytest.mark.wifi_connect
def test_multi_throughtput_tx(router_setting, request):
    tx_result = pytest.dut.get_tx_rate(router_setting, pytest.dut.rssi_num)
    logging.info(f'tx_result {tx_result}')
    expect_data = float(router_setting.expected_rate.split(' ')[0])
    logging.info(f'expect_data {expect_data}')
    request.node._store['return_value'] = (pytest.dut.channel, pytest.dut.rssi_num, expect_data, tx_result)
    assert all(float(x) > float(expect_data) for x in tx_result.split(','))


@pytest.mark.dependency(depends=["connect"])
@pytest.mark.wifi_connect
def test_multi_throughtput_rx(router_setting, request):
    rx_result = pytest.dut.get_rx_rate(router_setting, pytest.dut.rssi_num)
    logging.info(f'rx_result {rx_result}')
    expect_data = float(router_setting.expected_rate.split(' ')[1])
    logging.info(f'expect_data {expect_data}')
    request.node._store['return_value'] = (pytest.dut.channel, pytest.dut.rssi_num, expect_data, rx_result)
    assert all(float(x) > float(expect_data) for x in rx_result.split(','))
