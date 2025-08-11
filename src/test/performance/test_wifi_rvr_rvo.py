# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_wifi_rvr_rvo.py
# Time       ：2023/9/15 14:03
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import itertools
import logging
import re
import threading
import time
from src.test import get_testdata
from src.tools.rs_test import rs
import pytest

from src.tools.connect_tool.lab_device_controller import LabDeviceController
from src.tools.router_tool.Router import Router
from src.tools.router_tool.router_factory import get_router
from src.tools.config_loader import load_config

cfg = load_config()
router_name = cfg['router']['name']

# 实例路由器对象
router = get_router(router_name)
logging.info(f'router {router}')
test_data = get_testdata(router)

sum_list_lock = threading.Lock()

rvr_tool = cfg['rvr']['tool']

# 初始化 衰减 & 转台 对象

# 读取衰减 配置
rf_step_list = []
rf_ip = ''
rf_solution = cfg['rf_solution']
model = rf_solution['model']
if model not in ['RADIORACK-4-220', 'RC4DAT-8G-95', 'XIN-YI']:
    raise EnvironmentError("Doesn't support this model")
if model == 'XIN-YI':
    rf_tool = rs()
else:
    rf_ip = rf_solution[model]['ip_address']
    rf_tool = LabDeviceController(rf_ip)
    logging.info(f'rf_ip {rf_ip}')
rf_step_list = rf_solution['step']
rf_step_list = [i for i in range(*rf_step_list)][::3]
logging.info(f'rf_step_list {rf_step_list}')

corner_step_list = []
# 配置衰减
corner_ip = cfg['corner_angle']['ip_address']
if corner_ip == '192.168.5.11':
    corner_tool = rs()
else:
    corner_tool = LabDeviceController(corner_ip)
logging.info(f'corner_ip {corner_ip}')
corner_step_list = cfg['corner_angle']['step']
corner_step_list = [i for i in range(*corner_step_list)][::45]
logging.info(f'corner step_list {corner_step_list}')

step_list = itertools.product(corner_step_list, rf_step_list)

logging.info(f'finally step_list {step_list}')

# 配置 测试报告
# pytest.testResult.x_path = [] if (rf_needed and corner_needed) == 'both' else step_list
rx_result, tx_result = '', ''
throughput_threshold = float(cfg['rvr'].get('throughput_threshold', 0))
skip_tx = False
skip_rx = False


@pytest.fixture(scope='session', params=test_data, ids=[str(i) for i in test_data])
def setup(request):
    global rx_result, tx_result, pc_ip, dut_ip, skip_tx, skip_rx
    skip_tx = False
    skip_rx = False
    logging.info('router setup start')

    # 重置衰减&转台
    # 衰减器置0

    logging.info('Reset rf value')
    rf_tool.execute_rf_cmd(0)
    logging.info(rf_tool.get_rf_current_value())
    time.sleep(30)

    # 转台置0

    logging.info('Reset corner')
    corner_tool.set_turntable_zero()
    logging.info(corner_tool.get_turntanle_current_angle())
    time.sleep(3)

    # push_iperf()
    router_info = request.param

    # 修改路由器配置
    assert router.change_setting(router_info), "Can't set ap , pls check first"
    if pytest.connect_type == 'telnet':
        band = '5 GHz' if '2' in router_info.band else '2.4 GHz'
        ssid = router_info.ssid + "_bat";
        router.change_setting(Router(band=band, ssid=ssid))
    time.sleep(3)

    logging.info('router set done')
    with open(pytest.testResult.detail_file, 'a', encoding='utf-8') as f:
        f.write(f'Testing {router_info} \n')

    logging.info(f'dut try to connect {router_info.ssid}')
    if pytest.connect_type == 'telnet':
        connect_status = True
        time.sleep(90)
    else:
        # 连接 网络 最多三次重试
        for _ in range(3):
            try:
                type = 'wpa3' if 'WPA3' in router_info.authentication else 'wpa2'
                if router_info.authentication.lower() in \
                        ['open', '不加密', '无', 'open system', '无加密(允许所有人连接)', 'none']:
                    logging.info('no passwd')
                    cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, "open", "")
                else:
                    cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, type,
                                                             router_info.wpa_passwd)
                if router_info.hide_ssid == '是':
                    cmd += pytest.dut.CMD_WIFI_HIDE

                pytest.dut.checkoutput(cmd)
                time.sleep(5)

                if pytest.dut.wait_for_wifi_address(target=re.findall(r'(\d+\.\d+\.\d+\.)', dut_ip)[0]):
                    connect_status = True
                    break
            except Exception as e:
                logging.info(e)
                connect_status = False

    logging.info(f'dut_ip:{pytest.dut.dut_ip}')
    connect_status = True

    logging.info(f'pc_ip:{pytest.dut.pc_ip}')
    logging.info('dut connected')

    if rvr_tool == 'ixchariot':
        if '5' in router_info.band:
            pytest.dut.ix.modify_tcl_script("set script ",
                                            'set script "$ixchariot_installation_dir/Scripts/High_Performance_Throughput.scr"\n')
        else:
            pytest.dut.ix.modify_tcl_script("set script ",
                                            'set script "$ixchariot_installation_dir/Scripts/Throughput.scr"\n')
        pytest.dut.checkoutput(pytest.dut.IX_ENDPOINT_COMMAND)
        time.sleep(3)

    yield connect_status, router_info
    # 后置动作
    pytest.dut.kill_iperf()

    logging.info('Reset rf value')
    rf_tool.execute_rf_cmd(0)
    logging.info(rf_tool.get_rf_current_value())
    time.sleep(10)


# 测试 iperf
@pytest.mark.parametrize("rf_value", step_list)
def test_rvr(setup, rf_value):
    global rx_result, tx_result, skip_tx, skip_rx, throughput_threshold
    # 判断板子是否存在  ip
    if not setup[0]:
        logging.info("Can't connect wifi ,input 0")
        # rx_result_list.append('0')
        # tx_result_list.append('0')
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write("\n Can't connect wifi , skip this loop\n\n")
        return
    router_info = setup[1]

    # 执行 修改 步长
    # 修改衰减
    logging.info(f'set rf value {rf_value}')
    db_set = rf_value[1] if type(rf_value) == tuple else rf_value
    rf_tool.execute_rf_cmd(db_set)
    logging.info(rf_tool.get_rf_current_value())

    logging.info('set corner value')
    corner_set = rf_value[0] if type(rf_value) == tuple else rf_value
    corner_tool.execute_turntable_cmd('rt', angle=corner_set)
    logging.info(corner_tool.get_turntanle_current_angle())

    with open(pytest.testResult.detail_file, 'a') as f:
        f.write('-' * 40 + '\n')
        info = ''
        info += 'db_set : ' + str(db_set) + '\n'
        info += 'corner_set : ' + str(corner_set) + '\n'
        f.write(info)
    # time.sleep(1)

    # 获取rssi
    pytest.dut.get_rssi()
    if skip_tx:
        tx_result_info = (
            f'{pytest.dut.serialnumber} Throughput Standalone NULL Null {router_info.wireless_mode.split()[0]} '
            f'{router_info.band.split()[0]} {router_info.bandwidth.split()[0]} Rate_Adaptation '
            f'{router_info.channel} {type} UL NULL NULL {db_set} {pytest.dut.rssi_num} NULL NULL '
            f'"NULL" {",".join(map(str, [0]))}')
        logging.info(tx_result_info)
        pytest.testResult.save_result(tx_result_info.replace(' ', ','))
    if skip_rx:
        rx_result_info = (
            f'{pytest.dut.serialnumber} Throughput Standalone NULL Null {router_info.wireless_mode.split()[0]} '
            f'{router_info.band.split()[0]} {router_info.bandwidth.split()[0]} Rate_Adaptation '
            f'{router_info.channel} {type} DL NULL NULL {db_set} {pytest.dut.rssi_num} NULL NULL '
            f'"NULL" {",".join(map(str, [0]))}')
        pytest.testResult.save_result(rx_result_info.replace(' ', ','))
    if skip_tx and skip_rx:
        return
    # handle iperf pair count
    logging.info('start test iperf')
    logging.info(f'router_info: {router_info}')
    # iperf  打流
    if 'tx' in router_info.test_type and not skip_tx:
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        tx_result = pytest.dut.get_tx_rate(router_info, 'TCP', corner_tool=corner_tool, db_set=db_set)
        try:
            tx_val = float(tx_result.split(',')[0])
        except Exception:
            tx_val = 0
        if tx_val < throughput_threshold:
            skip_tx = True
    if 'rx' in router_info.test_type and not skip_rx:
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        rx_result = pytest.dut.get_rx_rate(router_info, 'TCP', corner_tool=corner_tool, db_set=db_set)
        try:
            rx_val = float(rx_result.split(',')[0])
        except Exception:
            rx_val = 0
        if rx_val < throughput_threshold:
            skip_rx = True
