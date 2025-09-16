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
    wait_for_dut_connection_recover,
)

_test_data = get_testdata(init_router())
router = init_router()
rf_tool = init_rf()
corner_tool = init_corner()


@pytest.fixture(scope='session', params=_test_data, ids=[str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    router_info = request.param
    connect_status = common_setup(router, router_info)
    yield connect_status, router_info
    pytest.dut.kill_iperf()
    logging.info('Reset rf value')
    rf_tool.execute_rf_cmd(0)
    logging.info(rf_tool.get_rf_current_value())
    time.sleep(10)


@pytest.fixture(scope="function", params=get_corner_step_list())
@log_fixture_params()
def setup_corner(request, setup_router):
    corner_set = request.param
    corner_tool.execute_turntable_cmd("rt", angle=corner_set)
    yield (
        setup_router[0],
        setup_router[1],
        corner_set
    )


@pytest.fixture(scope="function", params=get_rf_step_list())
@log_fixture_params()
def setup_attenuation(request, setup_corner):
    db_set = request.param
    connect_status, router_info, corner_set = setup_corner
    rf_tool.execute_rf_cmd(db_set)
    if connect_status:
        recover_status, _ = wait_for_dut_connection_recover()
        connect_status = connect_status and recover_status
    yield (connect_status, router_info, corner_set, db_set)
    pytest.dut.kill_iperf()


def test_rvr_rvo(setup_rf):
    connect_status, router_info, corner_set, db_set = setup_rf
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        return

    pytest.dut.get_rssi()
    logging.info('start test iperf')
    logging.info(f'router_info: {router_info}')
    if int(router_info.tx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_tx_rate(router_info, 'TCP', db_set=db_set, corner_set=corner_set)
    if int(router_info.rx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_rx_rate(router_info, 'TCP', db_set=db_set, corner_set=corner_set)
