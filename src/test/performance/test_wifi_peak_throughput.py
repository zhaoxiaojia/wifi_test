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
from src.tools.router_tool.Router import router_str
from src.util.constants import get_debug_flags

from src.test.performance import common_setup, init_router, scenario_group, wait_connect

_test_data = get_testdata(init_router())
router = init_router()


@pytest.fixture(scope='session', params=_test_data, ids=[router_str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    router_info = request.param
    common_setup(router, router_info)
    connect_status = wait_connect(router_info)
    debug_flags = get_debug_flags()
    if debug_flags.database_mode:
        logging.info(
            "Database debug mode enabled, use simulated throughput results for router %s",
            getattr(router_info, "ssid", "<unknown>"),
        )
    pytest.dut.get_rssi()
    yield connect_status, router_info
    pytest.dut.kill_iperf()


def test_rvr(setup_router, performance_sync_manager):
    connect_status, router_info = setup_router
    with scenario_group(router_info):
        if not connect_status:
            logging.info("Can't connect wifi ,input 0")
            return

        logging.info(f'start test iperf tx {router_info.tx} rx {router_info.rx}')
        debug_flags = get_debug_flags()
        rssi_num = pytest.dut.rssi_num
        if debug_flags.database_mode:
            logging.info(
                "Database debug mode enabled, skipping real iperf execution for router %s",
                getattr(router_info, "ssid", "<unknown>"),
            )
        if int(router_info.tx):
            logging.info(f'rssi : {rssi_num}')
            pytest.dut.get_tx_rate(router_info, 'TCP', debug=debug_flags.database_mode)
        if int(router_info.rx):
            logging.info(f'rssi : {rssi_num}')
            pytest.dut.get_rx_rate(router_info, 'TCP', debug=debug_flags.database_mode)

    performance_sync_manager(
        "Peak",
        pytest.testResult.log_file,
        message="Peak throught data rows stored in database",
    )
