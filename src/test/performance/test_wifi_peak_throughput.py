# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
File       : test_wifi_peak_throughput.py
Time       ：2023/9/15 14:03
Author     ：chao.li
version    ：python 3.9
Description：
"""

import logging
from src.test import get_testdata
from src.test.pyqt_log import log_fixture_params
import pytest

from src.test.performance import common_setup, init_router

_test_data = get_testdata(init_router())


@pytest.fixture(scope='session', params=_test_data, ids=[str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    router_info = request.param
    router = init_router()
    connect_status = common_setup(router, router_info)
    yield connect_status, router_info
    pytest.dut.kill_iperf()


def test_rvr(setup_router):
    connect_status, router_info = setup_router
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        return

    pytest.dut.get_rssi()
    logging.info('start test tx/rx')
    if int(router_info.tx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_tx_rate(router_info, 'TCP')
    if int(router_info.rx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_rx_rate(router_info, 'TCP')
