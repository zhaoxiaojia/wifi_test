# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
File       : test_wifi_rvo.py
Time       ：2023/9/15 14:03
Author     ：chao.li
version    ：python 3.9
Description：
"""

import logging
from src.test import get_testdata
from src.test.pyqt_log import log_fixture_params
import pytest

from src.test.performance import (
    common_setup,
    get_corner_step_list,
    init_corner,
    init_router,
)

_test_data = get_testdata(init_router())


@pytest.fixture(scope='session', params=_test_data, ids=[str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    router_info = request.param
    router = init_router()
    connect_status = common_setup(router, router_info)
    yield (connect_status, router_info)
    pytest.dut.kill_iperf()


@pytest.fixture(scope="function", params=get_corner_step_list())
@log_fixture_params()
def setup_corner(request, setup_router):
    value = request.param[0] if isinstance(request.param, tuple) else request.param
    corner_tool, step_list = init_corner()
    corner_tool.execute_turntable_cmd("rt", angle=value)
    yield setup_router[0], setup_router[1], value, corner_tool
    pytest.dut.kill_iperf()

def test_rvo(setup_corner):
    connect_status, router_info, corner_set, corner_tool = setup_corner
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        return

    rssi_num = pytest.dut.get_rssi()
    logging.info('start test tx/rx')
    logging.info(f'router_info: {router_info}')
    if int(router_info.tx):
        logging.info(f'rssi : {rssi_num} ')
        pytest.dut.get_tx_rate(router_info, 'TCP',
                               corner_tool=corner_tool,
                               db_set=db_set)
    if int(router_info.rx):
        logging.info(f'rssi : {rssi_num}')
        pytest.dut.get_rx_rate(router_info, 'TCP',
                               corner_tool=corner_tool,
                               db_set=db_set)
