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

router_name = load_config(refresh=True)['router']['name']

# 实例路由器对象
router = get_router(router_name)
logging.info(f'router {router}')
test_data = get_testdata(router)

sum_list_lock = threading.Lock()

rf_tool = None
corner_tool = None


# 配置 测试报告
# pytest.testResult.x_path = [] if (rf_needed and corner_needed) == 'both' else step_list


@pytest.fixture(scope='session', params=test_data, ids=[str(i) for i in test_data])
def setup(request):
    global pc_ip, dut_ip, rf_tool, corner_tool
    pytest.dut.skip_tx = False
    pytest.dut.skip_rx = False
    logging.info('router setup start')
    cfg = load_config(refresh=True)
    rvr_tool = cfg['rvr']['tool']

    rf_solution = cfg['rf_solution']
    print(f"rf_solution['step']: {rf_solution['step']}")
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
    print(f'rf_step_list {rf_step_list}')

    corner_ip = cfg['corner_angle']['ip_address']
    if corner_ip == '192.168.5.11':
        corner_tool = rs()
    else:
        corner_tool = LabDeviceController(corner_ip)
    logging.info(f'corner_ip {corner_ip}')
    corner_step = cfg['corner_angle']['step']
    print(f"corner_step: {corner_step}")
    corner_step_list = [i for i in range(*corner_step)][::45]
    print(f'corner_step_list {corner_step_list}')

    step_list = list(itertools.product(corner_step_list, rf_step_list))
    print(f'step_list {step_list}')

    logging.info('Reset rf value')
    rf_tool.execute_rf_cmd(0)
    logging.info(rf_tool.get_rf_current_value())
    time.sleep(30)

    logging.info('Reset corner')
    corner_tool.set_turntable_zero()
    logging.info(corner_tool.get_turntanle_current_angle())
    time.sleep(3)

    router_info = request.param

    # 修改路由器配置
    router.change_setting(router_info), "Can't set ap , pls check first"
    if pytest.connect_type == 'telnet':
        if router_info.band == "2.4G":
            router.change_country("欧洲")
        else:
            router.change_country("美国")
        band = '5G' if '2' in router_info.band else '2.4G'
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
                type = 'wpa3' if 'WPA3' in router_info.security_protocol else 'wpa2'
                if router_info.security_protocol.lower() in \
                        ['open', '不加密', '无', 'open system', '无加密(允许所有人连接)', 'none']:
                    logging.info('no passwd')
                    cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, "open", "")
                else:
                    cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, type,
                                                             router_info.password)
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

    yield connect_status, router_info, step_list
    # 后置动作
    pytest.dut.kill_iperf()

    logging.info('Reset rf value')
    rf_tool.execute_rf_cmd(0)
    logging.info(rf_tool.get_rf_current_value())
    time.sleep(10)


# 测试 iperf
def test_rvr(setup):
    connect_status, router_info, step_list = setup
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write("\n Can't connect wifi , skip this loop\n\n")
        return

    for rf_value in step_list:
        logging.info(f'set rf value {rf_value}')
        db_set = rf_value[1] if isinstance(rf_value, tuple) else rf_value
        rf_tool.execute_rf_cmd(db_set)
        logging.info(rf_tool.get_rf_current_value())

        logging.info('set corner value')
        corner_set = rf_value[0] if isinstance(rf_value, tuple) else rf_value
        corner_tool.execute_turntable_cmd('rt', angle=corner_set)
        logging.info(corner_tool.get_turntanle_current_angle())

        with open(pytest.testResult.detail_file, 'a') as f:
            f.write('-' * 40 + '\n')
            info = ''
            info += 'db_set : ' + str(db_set) + '\n'
            info += 'corner_set : ' + str(corner_set) + '\n'
            f.write(info)

        pytest.dut.get_rssi()
        logging.info('start test iperf')
        logging.info(f'router_info: {router_info}')
        if int(router_info.tx):
            logging.info(f'rssi : {pytest.dut.rssi_num}')
            pytest.dut.get_tx_rate(router_info, 'TCP', corner_tool=corner_tool, db_set=db_set)
        if int(router_info.rx):
            logging.info(f'rssi : {pytest.dut.rssi_num}')
            pytest.dut.get_rx_rate(router_info, 'TCP', corner_tool=corner_tool, db_set=db_set)
