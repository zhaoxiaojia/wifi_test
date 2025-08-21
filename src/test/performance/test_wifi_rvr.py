# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
File       : test_wifi_rvr.py
Time       ：2023/9/15 14:03
Author     ：chao.li
version    ：python 3.9
Description：
"""

import logging
import time
from src.test import get_testdata
from src.test.pyqt_log import log_fixture_params
import pytest

from src.test.performance import (
    common_setup,
    get_rf_step_list,
    init_rf,
    init_router,
)

test_data = get_testdata(init_router())
rf_step_list = get_rf_step_list()


@log_fixture_params()
@pytest.fixture(scope='session', params=test_data, ids=[str(i) for i in test_data])
def setup_router(request):
    router_info = request.param
    router = init_router()
    rf_tool, step_list = init_rf()
    connect_status = common_setup(router, router_info)
    try:
        yield connect_status, router_info, step_list, rf_tool
    finally:
        pytest.dut.kill_iperf()
        logging.info('Reset rf value')
        rf_tool.execute_rf_cmd(0)
        logging.info(rf_tool.get_rf_current_value())
        time.sleep(10)


@log_fixture_params()
@pytest.fixture(scope='function', params=rf_step_list)
def setup_rf(request, setup_router):
    db_set = request.param[1] if isinstance(request.param, tuple) else request.param
    rf_tool = setup_router[3]
    rf_tool.execute_rf_cmd(db_set)
    yield setup_router[0], setup_router[1], db_set, rf_tool


def test_rvr(setup_rf):
    connect_status, router_info, db_set, rf_tool = setup_rf
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write("\n Can't connect wifi , skip this loop\n\n")
        return
    with open(pytest.testResult.detail_file, 'a') as f:
        f.write('-' * 40 + '\n')
        info = ''
        info += 'db_set : ' + str(db_set) + '\n'
        info += 'corner_set : \n'
        f.write(info)

    pytest.dut.get_rssi()
    logging.info('start test iperf')
    if int(router_info.rx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_tx_rate(router_info, 'TCP', db_set=db_set)
    if int(router_info.tx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_rx_rate(router_info, 'TCP', db_set=db_set)
