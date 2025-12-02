import logging
import re
import subprocess
import time
import os
import json
import pytest

from src.tools.relay_tool.pdusnmp import power_ctrl
from src.tools.router_tool.Router import Router
from src.tools.router_tool.router_performance import (
    FPGA_CONFIG,
    compatibility_router,
    handle_expectdata as perf_handle_expectdata,
)
from src.tools.config_loader import load_config

power_delay = power_ctrl()
# power_delay.shutdown()
power_ctrl = power_delay.ctrl
router = ''
ssid = {
    '2.4G': 'Aml_AP_Comp_2.4G',
    '5G': 'Aml_AP_Comp_5G'
}
ssid_6g = 'Aml_AP_Comp_6G'
passwd = '@Aml#*st271'

# Project and chip info
project_cfg = pytest.config.get("project") or {}
wifi_module = str(project_cfg.get("wifi_module", "")).strip().upper()
interface = str(project_cfg.get("interface", "")).strip().upper()
pytest.chip_info = f"{wifi_module}_{interface}" if wifi_module or interface else ""
# Avoid shutting down power at import time; defer to fixture lifecycle.


@pytest.fixture(scope='module', autouse=True, params=power_ctrl, ids=[str(i) for i in power_ctrl])
def power_setting(request):
    ip, port = request.param
    power_delay.switch(ip, port, 1)
    time.sleep(30)
    # logging.info(f'port {port} ip {ip}')
    # logging.info(compatibility_router._instances)
    try:
        info = [x for x in filter(lambda x: str(x.get('port')) == str(port) and x.get('ip') == ip, compatibility_router._instances)]
    except Exception:
        info = []
    if not info:
        raise RuntimeError(f"Router info not found for ip={ip} port={port}")
    yield info[0]
    logging.info('test done shutdown the router')
    power_delay.switch(ip, port, 2)


@pytest.fixture(scope='module', autouse=True, params=['2.4G', '5G'], ids=['2.4G', '5G'])
def router_setting(power_setting, request):
    if not power_setting:
        raise ValueError("Pls check pdu ip address and router port")
    try:
        nic = load_config(refresh=True).get("compatibility", {}).get("nic") or "eth1"
    except Exception:
        nic = "eth1"
    pytest.dut.pc_ip = pytest.host_os.dynamic_flush_network_card(nic)
    if pytest.dut.pc_ip is None:
        assert False, "Can't get pc ip address"
    logging.info(f'pc_ip {pytest.dut.pc_ip}')
    router_set = power_setting
    band = request.param
    expect_tx = perf_handle_expectdata(router_set, band, 'UL', pytest.chip_info)
    expect_rx = perf_handle_expectdata(router_set, band, 'DL', pytest.chip_info)
    router_obj = Router(
        band=band,
        wireless_mode=router_set[band]['mode'],
        channel='default',
        security_mode=router_set[band].get('security_mode'),
        bandwidth=router_set[band]['bandwidth'],
        ssid=ssid[band],
        password=passwd,
        expected_rate=f'{expect_tx} {expect_rx}',
    )
    logging.info(f'router yield {router_obj}')
    yield router_obj


@pytest.mark.dependency(name="scan")
def test_scan(router_setting):
    result = 'FAIL'
    if pytest.connect_type == 'telnet':
        result = 'PASS' if pytest.dut.roku.flush_ip() else 'FAIL'
        assert result =='PASS',f"Can't be reconnected"
        logging.info(f'dut_ip: {pytest.dut.roku.flush_ip()}')
    # pytest.dut.push_iperf()
    result = 'PASS' if pytest.dut.wifi_scan(router_setting.ssid) else 'FAIL'
    assert result == 'PASS', f"Can't scan target ssid {router_setting.ssid}"


@pytest.mark.dependency(name="connect", depends=["scan"])
def test_connect(router_setting):
    result = 'FAIL'
    pytest.dut.forget_wifi()
    pytest.dut.connect_ssid(router_setting)
    result = 'PASS' if pytest.dut.wait_for_wifi_address()[0] else 'FAIL'
    pytest.dut.get_rssi()
    if router_setting.band == '5G':
        assert pytest.dut.freq_num > 5000
    if router_setting.band == '2.4G':
        assert pytest.dut.freq_num < 5000
    # Update channel attribute directly for downstream tests.
    try:
        router_setting.channel = pytest.dut.channel
    except Exception:
        pass
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
