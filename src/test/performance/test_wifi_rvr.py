#!/usr/bin/env python
# -*-coding:utf-8 -*-

"""
File       : test_wifi_rvr.py
Time       : 2023/9/15 14:03
Author     : chao.li
version    : python 3.9
Description:
"""

import logging

import pytest

from src.test import get_testdata
from src.test.pyqt_log import log_fixture_params
from src.test.performance import common_setup, ensure_performance_result, get_cfg, get_rf_step_list, init_rf, init_router, scenario_group, wait_connect
from src.tools.router_tool.Router import router_str

_test_data = get_testdata(init_router())
rf_tool = init_rf()


@pytest.fixture(scope="session", params=_test_data, ids=[router_str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    router_info = request.param
    router = init_router()
    common_setup(router, router_info)
    rf_tool.execute_rf_cmd(0)
    connect_status = wait_connect(router_info)
    yield router_info, connect_status
    pytest.dut.kill_iperf()
    rf_tool.execute_rf_cmd(0)


@pytest.fixture(scope="function", params=get_rf_step_list())
@log_fixture_params()
def setup_attenuation(request, setup_router):
    db_set = request.param
    router_info, connect_status = setup_router
    rf_tool.execute_rf_cmd(db_set)
    logging.info("Set attenuation: %s dB", rf_tool.get_rf_current_value())
    pytest.dut.get_rssi()
    yield connect_status, router_info, db_set
    pytest.dut.kill_iperf()


def test_rvr(setup_attenuation, performance_sync_manager):
    connect_status, router_info, db_set = setup_attenuation
    test_result = ensure_performance_result()
    with scenario_group(router_info):
        test_result.ensure_log_file_prefix("RVR")
        if not connect_status:
            logging.info("Cannot connect to Wi-Fi, skip remaining steps")
        else:
            logging.info("Start iperf test tx %s rx %s", router_info.tx, router_info.rx)

            if int(router_info.tx):
                logging.info("RSSI during TX: %s", pytest.dut.rssi_num)
                pytest.dut.get_tx_rate(router_info, "TCP", db_set=db_set)
            if int(router_info.rx):
                logging.info("RSSI during RX: %s", pytest.dut.rssi_num)
                pytest.dut.get_rx_rate(router_info, "TCP", db_set=db_set)

    performance_sync_manager(
        "RVR",
        test_result.log_file,
        message="RVR data rows stored in database",
    )
