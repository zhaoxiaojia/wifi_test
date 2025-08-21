# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
File       : test_wifi_rvr_rvo.py
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
    get_corner_step_list,
    get_rf_step_list,
    init_corner,
    init_rf,
    init_router,
)

test_data = get_testdata(init_router())
rf_step_list = get_rf_step_list()
corner_step_list = get_corner_step_list()


@log_fixture_params()
@pytest.fixture(scope='session', params=test_data, ids=[str(i) for i in test_data])
def setup_router(request):
    router_info = request.param
    router = init_router()
    rf_tool, rf_list = init_rf()
    corner_tool, corner_list = init_corner()
    connect_status = common_setup(router, router_info)
    step_list = (corner_list, rf_list)
    tools = (rf_tool, corner_tool)
    try:
        yield connect_status, router_info, step_list, tools
    finally:
        pytest.dut.kill_iperf()
        logging.info('Reset rf value')
        rf_tool.execute_rf_cmd(0)
        logging.info(rf_tool.get_rf_current_value())
        time.sleep(10)


@log_fixture_params()
@pytest.fixture(scope="function", params=corner_step_list)
def setup_corner(request, setup_router):
    corner_set = request.param[0] if isinstance(request.param, tuple) else request.param
    rf_step_list = setup_router[2][1]
    rf_tool, corner_tool = setup_router[3]
    corner_tool.execute_turntable_cmd("rt", angle=corner_set)
    yield (
        setup_router[0],
        setup_router[1],
        corner_set,
        corner_tool,
        rf_step_list,
        rf_tool,
    )


@log_fixture_params()
@pytest.fixture(scope="function", params=rf_step_list)
def setup_rf(request, setup_corner):
    db_set = request.param[1] if isinstance(request.param, tuple) else request.param
    connect_status, router_info, corner_set, corner_tool, _, rf_tool = setup_corner
    rf_tool.execute_rf_cmd(db_set)
    yield connect_status, router_info, corner_set, db_set, rf_tool, corner_tool


def test_rvr_rvo(setup_rf):
    connect_status, router_info, corner_set, db_set, rf_tool, corner_tool = setup_rf
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write("\n Can't connect wifi , skip this loop\n\n")
        return

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
