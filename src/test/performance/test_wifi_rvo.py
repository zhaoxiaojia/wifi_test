#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RVO performance test flow with streamlined fixture handling."""

import logging
import time
from collections import namedtuple
from typing import Optional, Tuple

import pytest
from src.tools.router_tool.Router import router_str

from src.test import get_testdata
from src.test.pyqt_log import log_fixture_params, update_fixture_params
from src.test.performance import (
    common_setup,
    get_corner_step_list,
    get_rvo_static_db_list,
    get_rvo_target_rssi_list,
    init_corner,
    init_rf,
    init_router,
    wait_connect,
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
    step = 10
    logging.info(
        'Start adjusting attenuation to %s dB for target RSSI %s dBm',
        applied_db,
        target_rssi,
    )
    current_rssi = pytest.dut.get_rssi()
    if current_rssi == -1:
        return current_rssi, applied_db

    def _get_diff_sign(value: int) -> int:
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    diff = current_rssi - target_rssi
    previous_diff_sign = _get_diff_sign(diff)

    for attempt in range(max_iterations):
        logging.info('current rssi %s target rssi %s', current_rssi, target_rssi)
        if abs(diff) <= tolerance:
            break

        current_diff_sign = previous_diff_sign
        if diff < -tolerance:
            direction = 1
        elif diff > tolerance:
            direction = -1
        else:
            break
        next_db = applied_db + direction * step
        next_db = max(0, min(110, next_db))
        no_adjustment_possible = next_db == applied_db
        overshoot_detected = no_adjustment_possible

        applied_db = next_db
        logging.info(
            'Adjust attenuation to %s dB (attempt %s) for RSSI %s dBm -> target %s dBm',
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
        diff = current_rssi - target_rssi
        new_diff_sign = _get_diff_sign(diff)
        if abs(diff) <= tolerance:
            previous_diff_sign = new_diff_sign
            break
        if diff < -tolerance:
            direction = 1
        elif diff > tolerance:
            direction = -1
        else:
            break
        if (
            current_diff_sign != 0
            and new_diff_sign != 0
            and new_diff_sign != current_diff_sign
        ):
            overshoot_detected = True
        previous_diff_sign = new_diff_sign

        if applied_db == 0 and direction == -1 and no_adjustment_possible:
            logging.info(
                'Attenuation already at 0 dB but RSSI %s dBm above target %s dBm, continue test.',
                current_rssi,
                target_rssi,
            )
            break

        if overshoot_detected:
            new_step = step // 2 if step > 1 else 1
            step = max(new_step, 1)
            if step == 0:
                break
            if no_adjustment_possible and step == 1 and applied_db in (0, 110):
                break
            continue

    logging.info('Final RSSI %s dBm with attenuation %s dB', current_rssi, applied_db)
    return current_rssi, applied_db


RVOProfile = namedtuple("RVOProfile", "mode value")
RVOCase = namedtuple("RVOCase", "profile corner")

_MODE_DEFAULT = "default"
_MODE_STATIC = "static"
_MODE_TARGET = "target"


def _profile_id(profile: RVOProfile) -> str:
    if profile.mode == _MODE_STATIC:
        return f'static-{profile.value}'
    if profile.mode == _MODE_TARGET:
        return f'target-{profile.value}'
    return _MODE_DEFAULT


def _case_id(case: RVOCase) -> str:
    return f'{_profile_id(case.profile)}|corner-{case.corner}'


def _get_rvo_profiles() -> list[RVOProfile]:
    static_values = [value for value in get_rvo_static_db_list() if value is not None]
    target_values = [value for value in get_rvo_target_rssi_list() if value is not None]

    if static_values and target_values:
        logging.error(
            'Both corner_angle.static_db %s and corner_angle.target_rssi %s detected; '
            'only one group is supported. Target RSSI values take precedence.',
            static_values,
            target_values,
        )
        static_values = []

    if static_values:
        return [RVOProfile(_MODE_STATIC, value) for value in static_values]
    if target_values:
        return [RVOProfile(_MODE_TARGET, value) for value in target_values]
    return [RVOProfile(_MODE_DEFAULT, None)]


def _build_rvo_cases() -> list[RVOCase]:
    profiles = _get_rvo_profiles()
    corners = get_corner_step_list() or [0]
    return [RVOCase(profile, corner) for profile in profiles for corner in corners]


RVO_CASES = _build_rvo_cases()
RVO_CASE_IDS = [_case_id(case) for case in RVO_CASES]


def _apply_static_attenuation(static_db: Optional[int]) -> Tuple[int, Optional[int]]:
    if static_db is None:
        measured = pytest.dut.get_rssi()
        return measured, None
    logging.info('Set static attenuation to %s dB before RVO test.', static_db)
    try:
        rf_tool.execute_rf_cmd(static_db)
    except Exception as exc:
        logging.warning('Failed to set static attenuation %s dB: %s', static_db, exc)
    measured = pytest.dut.get_rssi()
    return measured, static_db


def _apply_profile(profile: RVOProfile) -> Tuple[int, Optional[int]]:
    if profile.mode == _MODE_STATIC:
        return _apply_static_attenuation(profile.value)
    if profile.mode == _MODE_TARGET:
        return _adjust_rssi_to_target(profile.value, None)
    measured = pytest.dut.get_rssi()
    return measured, None


router = init_router()
corner_tool = init_corner()
rf_tool = init_rf()
_test_data = get_testdata(router)


@pytest.fixture(scope='session', params=_test_data, ids=[router_str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    router_info = request.param
    common_setup(router, router_info)
    connect_status = wait_connect(router_info)
    yield connect_status, router_info
    pytest.dut.kill_iperf()


@pytest.fixture(scope='function', params=RVO_CASES, ids=RVO_CASE_IDS)
@log_fixture_params()
def setup_rvo_case(request, setup_router):
    connect_status, router_info = setup_router
    case: RVOCase = request.param
    profile = case.profile
    corner_angle = case.corner

    corner_tool.execute_turntable_cmd('rt', angle=corner_angle)
    corner_tool.get_turntanle_current_angle()
    measured_rssi, attenuation_db = _apply_profile(profile)

    update_fixture_params(
        request,
        {
            'corner': corner_angle,
            'mode': profile.mode,
            'value': profile.value,
            'attenuation_db': attenuation_db,
            'rssi': measured_rssi,
        },
    )

    try:
        yield connect_status, router_info, corner_angle, attenuation_db, measured_rssi, profile
    finally:
        pytest.dut.kill_iperf()


def test_rvo(setup_rvo_case, performance_sync_manager):
    connect_status, router_info, corner_angle, attenuation_db, rssi_num, profile = setup_rvo_case
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        return

    logging.info('RVO profile %s', _profile_id(profile))
    logging.info('corner angle set to %s', corner_angle)
    logging.info('start test iperf tx %s rx %s', router_info.tx, router_info.rx)

    if int(router_info.tx):
        logging.info('rssi : %s', rssi_num)
        pytest.dut.get_tx_rate(
            router_info,
            'TCP',
            corner_tool=corner_tool,
            db_set='' if attenuation_db is None else attenuation_db,
        )
    if int(router_info.rx):
        logging.info('rssi : %s', rssi_num)
        pytest.dut.get_rx_rate(
            router_info,
            'TCP',
            corner_tool=corner_tool,
            db_set='' if attenuation_db is None else attenuation_db,
        )

    # performance_sync_manager(
    #     "RVO",
    #     pytest.testResult.log_file,
    #     message="RVO data rows stored in database",
    # )
