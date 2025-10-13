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
from src.test.pyqt_log import log_fixture_params, update_fixture_params
# from src.tools.mysql_tool.MySqlControl import sync_file_to_db
from src.test.performance import (
    common_setup,
    get_cfg,
    get_rf_step_list,
    init_rf,
    init_router, wait_connect,
)
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
    yield router_info
    pytest.dut.kill_iperf()


@pytest.fixture(scope="function", params=get_rf_step_list())
@log_fixture_params()
def setup_attenuation(request, setup_router):
    db_set = request.param
    router_info = setup_router

    rf_tool.execute_rf_cmd(db_set)
    logging.info("Set attenuation: %s dB", rf_tool.get_rf_current_value())
    connect_status = wait_connect(router_info)
    pytest.dut.get_rssi()
    yield connect_status, router_info, db_set
    pytest.dut.kill_iperf()


def test_rvr(setup_attenuation):
    connect_status, router_info, db_set = setup_attenuation
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

    # if not getattr(pytest, "_rvr_data_synced", False):
    #     rows_stored = sync_file_to_db(pytest.testResult.log_file, "RVR")
    #     if rows_stored:
    #         logging.info("RVR data rows stored in database: %s", rows_stored)
    #     pytest._rvr_data_synced = True
