import logging
import re
import subprocess
import time
import os
import json
import pytest

from tools.pdusnmp import power_ctrl
from tools.router_tool.Router import Router
from tools.router_tool.router_performance import fpga, compatibility_data

power_delay = power_ctrl()
power_ctrl = power_delay.ctrl
router = ''
ssid_2g = 'Aml_AP_Comp_2.4G'
ssid_5g = 'Aml_AP_Comp_5G'
ssid_6g = 'Aml_AP_Comp_6G'
passwd = '@Aml#*st271'
dut_wifichip = 'w1'
router_2g = Router(band='2.4 GHz', wireless_mode='11ac', channel='1', authentication_method='Open System',
                   bandwidth='20 MHz', ssid=ssid_2g, wpa_passwd=passwd, expected_rate='10 10')

router_5g = Router(band='5 GHz', wireless_mode='11ac', channel='36', authentication_method='Open System',
                   bandwidth='20 MHz', ssid=ssid_5g, wpa_passwd=passwd, expected_rate='10 10')

wifichip, interface = pytest.chip_info.split('_')

def handle_expectdata(ip, port, band, bandwidth, dir):
    '''

    Args:
        ip: the ip address of the pdu
        port: the port of router,value ranges from 0-8
        band: the frequency band for Wi-Fi, only can be 2.4G or 5G
        bandwidth: the bandwidth of Wi-Fi
        dir: the direction of the throughput

    Returns:

    '''
    # with open(f"{os.getcwd()}/config/compatobility_expectdata.json", 'r') as f:
    with open(f"compatobility_expectdata.json", 'r') as f:
        router_datas = json.load(f)
    for data in router_datas:
        if data['ip'] == ip and data['port'] == port:
            return data[band][interface][fpga[wifichip][band]][bandwidth][fpga[wifichip]['mimo']][dir]


@pytest.fixture(scope="session")
def test_results():
    """全局存储测试方法的返回值和执行结果"""
    return {}


@pytest.fixture
def record_result(request, test_results):
    """Fixture 用于存储单个测试的返回值"""

    def store(value):
        test_results[request.node.nodeid] = {
            "return_value": value,
            "result": None  # 先存储返回值，测试结果稍后更新
        }

    return store


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """在测试完成后记录测试结果（passed/failed）"""
    outcome = yield
    report = outcome.get_result()

    if call.when == "call":  # 仅记录测试方法执行阶段
        if hasattr(item.session, "test_results") and item.nodeid in item.session.test_results:
            item.session.test_results[item.nodeid]["result"] = report.outcome


@pytest.fixture(scope='session', autouse=True)
def power_shotdown(request, test_results):
    power_delay.shutdown()
    time.sleep(2)
    yield
    print("\n=== 测试结果汇总 ===")
    for test_name, data in test_results.items():
        print(f"Test: {test_name}, Result: {data['result']}, Return Value: {data['return_value']}")


@pytest.fixture(scope='module', autouse=True, params=power_ctrl, ids=[str(i) for i in power_ctrl])
def power_setting(request):
    ip, port = request.param
    power_delay.switch(ip, port, 1)
    time.sleep(60)
    yield [x for x in filter(lambda x: x.port == port and x.ip == ip, compatibility_data._instances)]
    power_delay.switch(ip, port, 2)


@pytest.fixture(scope='module', autouse=True, params=['2.4G', '5G'], ids=['2.4G', '5G'])
def router_setting(power_setting, request):
    pc_ip = pytest.host_os.dynamic_flush_network_card('eth0')
    if pc_ip is None: assert False, "Can't get pc ip address"
    pytest.dut.ip_target = '.'.join(pc_ip.split('.')[:3])
    logging.info(f'pc_ip {pc_ip}')
    router_set = power_setting[0]['data']
    band = request.param
    expect_tx = handle_expectdata(router_set.ip, router_set.port, band, router_set.bandwidth, 'UL')
    expect_rx = handle_expectdata(router_set.ip, router_set.port, band, router_set.bandwidth, 'DL')
    router = Router(band=band, wireless_mode=router_set.mode, channel='default',
                    authentication_method=router_set.authentication,
                    bandwidth=router_set.bandwidth, ssid=ssid_2g, wpa_passwd=passwd,
                    expected_rate=f'{expect_tx} {expect_rx}')
    yield router


@pytest.mark.dependency(name="scan")
def test_scan(router_setting, record_result):
    pytest.dut.push_iperf()
    for _ in range(5):
        info = pytest.dut.checkoutput("cmd wifi start-scan;cmd wifi list-scan-results")
        logging.info(info)
        if router.ssid in info:
            break;
        time.sleep(3)
    else:
        assert False, f"Can't scan target ssid {router.ssid}"
    record_result(None)


@pytest.mark.dependency(name="connect", depends=["scan"])
def test_connect(router_setting, record_result):
    pytest.dut.forget_wifi()
    pytest.dut.checkoutput(pytest.dut.get_wifi_cmd(router))
    assert pytest.dut.wait_for_wifi_address()[0], "Can't connect ssid"
    record_result(None)


@pytest.mark.dependency(depends=["connect"])
@pytest.mark.wifi_connect
def test_multi_throughtput_tx(router_setting, record_result):
    router_info = router_setting
    rssi_num = pytest.dut.get_rssi()
    tx_result = pytest.dut.get_tx_rate(router_info, rssi_num)
    logging.info(tx_result)
    for i in tx_result:
        if i >= float(router.expected_rate[0]):
            break
    else:
        assert False, 'Rate too low'
    time.sleep(5)
    record_result(tx_result)


@pytest.mark.dependency(depends=["connect"])
@pytest.mark.wifi_connect
def test_multi_throughtput_rx(router_setting, record_result):
    router_info = router_setting
    rssi_num = pytest.dut.get_rssi()
    rx_result = pytest.dut.get_rx_rate(router_info, rssi_num)
    logging.info(rx_result)
    for i in rx_result:
        if i >= float(router.expected_rate[1]):
            break
    else:
        assert False, 'Rate too low'
    time.sleep(5)
    record_result(rx_result)
