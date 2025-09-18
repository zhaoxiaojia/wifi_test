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
import time
from typing import Optional, Tuple

import pytest

from src.test import get_testdata
from src.test.pyqt_log import log_fixture_params
from src.test.performance import (
    common_setup,
    get_corner_step_list,
    get_rvo_static_db_list,
    get_rvo_target_rssi_list,
    init_corner,
    init_rf,
    init_router,
)


def _safe_int(value) -> Optional[int]:
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return int(float(value))
        except ValueError:
            return None
    if isinstance(value, (list, tuple, set)):
        for item in value:
            parsed = _safe_int(item)
            if parsed is not None:
                return parsed
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _get_current_attenuation() -> int:
    try:
        value = rf_tool.get_rf_current_value()
    except Exception as exc:
        logging.warning('Failed to get rf current value: %s', exc)
        return 0
    parsed = _safe_int(value)
    return parsed if parsed is not None else 0


def _adjust_rssi_to_target(target_rssi: int, base_db: Optional[int]) -> Tuple[int, Optional[int]]:
    tolerance = 1
    max_iterations = 20
    applied_db = base_db if base_db is not None else _get_current_attenuation()
    applied_db = max(0, min(110, applied_db))
    logging.info(
        'Start adjusting attenuation to %s dB for target RSSI %s dBm',
        applied_db,
        target_rssi,
    )
    current_rssi = pytest.dut.get_rssi()
    if current_rssi == -1:
        return current_rssi, applied_db

    for attempt in range(max_iterations):
        if abs(current_rssi - target_rssi) <= tolerance:
            break

        if current_rssi < target_rssi:
            next_db = max(0, applied_db - 1)
        else:
            next_db = min(110, applied_db + 1)

        if next_db == applied_db:
            break

        applied_db = next_db
        logging.info(
            'Adjust attenuation to %s dB (attempt %s) for RSSI %s dBm → target %s dBm',
            applied_db,
            attempt + 1,
            current_rssi,
            target_rssi,
        )
        try:
            rf_tool.execute_rf_cmd(applied_db)
        except Exception as exc:
            logging.warning('Failed to execute rf command %s: %s', applied_db, exc)
            break
        time.sleep(3)
        current_rssi = pytest.dut.get_rssi()
        if applied_db == 0 and current_rssi < target_rssi - tolerance:
            logging.info(
                'Attenuation already at 0 dB but RSSI %s dBm below target %s dBm, continue test.',
                current_rssi,
                target_rssi,
            )
            break

    logging.info('Final RSSI %s dBm with attenuation %s dB', current_rssi, applied_db)
    return current_rssi, applied_db


router = init_router()
corner_tool = init_corner()
rf_tool = init_rf()
_test_data = get_testdata(router)


@pytest.fixture(scope='session', params=_test_data, ids=[str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    router_info = request.param
    connect_status = common_setup(router, router_info)
    yield connect_status, router_info
    pytest.dut.kill_iperf()


@pytest.fixture(scope='function', params=get_corner_step_list())
@log_fixture_params()
def setup_corner(request, setup_router):
    corner_set = request.param[0] if isinstance(request.param, tuple) else request.param
    corner_tool.execute_turntable_cmd('rt', angle=corner_set)
    yield setup_router[0], setup_router[1], corner_tool, corner_set
    pytest.dut.kill_iperf()


@pytest.fixture(scope='function', params=get_rvo_static_db_list())
@log_fixture_params()
def setup_static_db(request, setup_corner):
    connect_status, router_info, corner_tool_obj, corner_set = setup_corner
    static_db = request.param
    applied_db = static_db
    if static_db is None:
        logging.info('No static attenuation configured, skip setting attenuation.')
    else:
        logging.info('Set static attenuation to %s dB before RVO test.', static_db)
        try:
            rf_tool.execute_rf_cmd(static_db)
        except Exception as exc:
            logging.warning('Failed to set static attenuation %s dB: %s', static_db, exc)
            applied_db = None
    yield connect_status, router_info, corner_tool_obj, corner_set, applied_db


@pytest.fixture(scope='function', params=get_rvo_target_rssi_list())
@log_fixture_params()
def setup_rssi(request, setup_static_db):
    connect_status, router_info, corner_tool_obj, corner_set, static_db = setup_static_db
    target_rssi = request.param
    if target_rssi is None:
        logging.info('No target RSSI configured, skip attenuation adjustment.')
        measured_rssi = pytest.dut.get_rssi()
        final_db = static_db
    else:
        measured_rssi, final_db = _adjust_rssi_to_target(target_rssi, static_db)
    yield connect_status, router_info, corner_tool_obj, corner_set, final_db, measured_rssi


def test_rvo(setup_rssi):
    connect_status, router_info, corner_tool_obj, corner_set, attenuation_db, rssi_num = setup_rssi
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        return

    logging.info('corner angle set to %s', corner_set)
    if attenuation_db is not None:
        logging.info('attenuation set to %s dB', attenuation_db)
    logging.info(f'start test iperf tx {router_info.tx} rx {router_info.rx}')
    if int(router_info.tx):
        logging.info(f'rssi : {rssi_num}')
        pytest.dut.get_tx_rate(
            router_info,
            'TCP',
            corner_tool=corner_tool_obj,
            db_set='' if attenuation_db is None else attenuation_db,
        )
    if int(router_info.rx):
        logging.info(f'rssi : {rssi_num}')
        pytest.dut.get_rx_rate(
            router_info,
            'TCP',
            corner_tool=corner_tool_obj,
            db_set='' if attenuation_db is None else attenuation_db,
        )
