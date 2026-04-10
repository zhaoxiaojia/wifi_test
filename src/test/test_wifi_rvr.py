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
from src.test.pyqt_log import update_fixture_params
from src.test import (
    adjust_rssi_to_target,
    common_setup,
    ensure_performance_result,
    get_rf_step_list,
    get_target_rssi_list,
    init_rf,
    init_router,
    scenario_group,
    wait_connect,
)
from src.tools.router_tool.Router import router_str

_test_data = get_testdata(init_router())
rf_tool = init_rf()
RVR_TARGET_RSSI = next((value for value in get_target_rssi_list() if value is not None), None)
RVR_ATTENUATION_CASES = (
    [RVR_TARGET_RSSI] if RVR_TARGET_RSSI is not None else get_rf_step_list()
)


@pytest.fixture(scope="session", params=_test_data, ids=[router_str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    rf_tool.execute_rf_cmd(0)
    router_info = request.param
    router = init_router()
    common_setup(router, router_info)
    connect_status = wait_connect(router_info)
    yield router_info, connect_status
    pytest.dut.kill_iperf()
    rf_tool.execute_rf_cmd(0)


@log_fixture_params()
def setup_attenuation(request, setup_router):
    router_info, connect_status = setup_router
    if RVR_TARGET_RSSI is not None:
        measured_rssi, db_set = adjust_rssi_to_target(rf_tool, RVR_TARGET_RSSI, None)
        update_fixture_params(
            request,
            {
                "mode": "target",
                "value": RVR_TARGET_RSSI,
                "attenuation_db": db_set,
                "rssi": measured_rssi,
            },
        )
        yield connect_status, router_info, db_set, measured_rssi
    else:
        db_set = request.param
        rf_tool.execute_rf_cmd(db_set)
        current_value = rf_tool.get_rf_current_value()
        logging.info("Set attenuation: %s dB", current_value)
        measured_rssi = pytest.dut.get_rssi()
        yield connect_status, router_info, db_set, measured_rssi
    pytest.dut.kill_iperf()


setup_attenuation = pytest.fixture(scope="function", params=RVR_ATTENUATION_CASES)(setup_attenuation)


def test_rvr(setup_attenuation, performance_sync_manager):
    connect_status, router_info, db_set, measured_rssi = setup_attenuation
    test_result = ensure_performance_result()
    with scenario_group(router_info):
        test_result.ensure_log_file_prefix("RVR")
        if RVR_TARGET_RSSI is not None:
            test_result.set_active_profile("target", RVR_TARGET_RSSI)
        if not connect_status:
            logging.info("Cannot connect to Wi-Fi, skip remaining steps")
        else:
            logging.info("Start iperf test tx %s rx %s", router_info.tx, router_info.rx)

            if int(router_info.tx):
                logging.info("RSSI during TX: %s", measured_rssi)
                pytest.dut.get_tx_rate(router_info, "TCP", db_set=db_set)

                ext_rssi = getattr(pytest.dut, '_extended_rssi_result', None)
                mcs_tx = getattr(pytest.dut, '_mcs_tx_result', "N/A")
                mcs_rx = getattr(pytest.dut, '_mcs_rx_result', "N/A")

                if ext_rssi:
                    bcn, wf0, wf1 = ext_rssi
                    logging.info(f"TX Extended RSSI => bcn: {bcn}, wf0: {wf0}, wf1: {wf1}")

            if int(router_info.rx):
                logging.info("RSSI during RX: %s", measured_rssi)
                pytest.dut.get_rx_rate(router_info, "TCP", db_set=db_set)
                ext_rssi = getattr(pytest.dut, '_extended_rssi_result', None)
                mcs_tx = getattr(pytest.dut, '_mcs_tx_result', "N/A")
                mcs_rx = getattr(pytest.dut, '_mcs_rx_result', "N/A")

                if ext_rssi:
                    bcn, wf0, wf1 = ext_rssi
                    logging.info(f"TX Extended RSSI => bcn: {bcn}, wf0: {wf0}, wf1: {wf1}")
        test_result.clear_active_profile()

    performance_sync_manager(
        "RVR",
        test_result.log_file,
        message="RVR data stored",
    )
