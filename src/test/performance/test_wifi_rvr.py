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

_test_data = get_testdata(init_router())
rf_tool = init_rf()


@pytest.fixture(scope='session', params=_test_data, ids=[str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    router_info = request.param
    router = init_router()
    connect_status = common_setup(router, router_info)
    yield connect_status, router_info
    pytest.dut.kill_iperf()
    logging.info('Reset rf value')
    rf_tool.execute_rf_cmd(0)
    logging.info(rf_tool.get_rf_current_value())
    time.sleep(30)


@pytest.fixture(scope='function', params=get_rf_step_list())
@log_fixture_params()
def setup_attenuation(request, setup_router):
    db_set = request.param
    connect_status, router_info = setup_router
    rf_tool.execute_rf_cmd(db_set)
    yield (connect_status, router_info, db_set)
    pytest.dut.kill_iperf()


def test_rvr(setup_attenuation):
    connect_status, router_info, db_set = setup_attenuation
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        return


    pytest.dut.get_rssi()
    logging.info('start test iperf')

    if int(router_info.tx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_tx_rate(router_info, 'TCP', db_set=db_set)
    if int(router_info.rx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_rx_rate(router_info, 'TCP', db_set=db_set)
