#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RVO performance test flow with streamlined fixture handling."""

import logging
import time
from collections import namedtuple
from typing import Optional, Tuple

import pytest
from src.tools.router_tool.Router import router_str
from src.util.constants import (
    TURN_TABLE_FIELD_STATIC_DB,
    TURN_TABLE_FIELD_TARGET_RSSI,
    TURN_TABLE_SECTION_KEY,
    get_debug_flags,
)

from src.test import get_testdata
from src.test.pyqt_log import log_fixture_params, update_fixture_params
from src.test.performance import (
    common_setup,
    describe_debug_reason,
    ensure_performance_result,
    get_corner_step_list,
    get_rf_step_list,
    get_rvo_static_db_list,
    get_rvo_target_rssi_list,
    init_corner,
    init_rf,
    init_router,
    scenario_group,
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


def _clamp_db(value: Optional[int]) -> int:
    parsed = _safe_int(value)
    if parsed is None:
        return 0
    return max(0, min(110, parsed))


def _initial_step_size() -> int:
    try:
        candidates = sorted(set(get_rf_step_list()))
    except Exception as exc:
        logging.warning('Failed to load RF step list: %s; fallback to step=1', exc)
        return 1

    max_gap = 0
    previous = None
    for value in candidates:
        if previous is not None and value > previous:
            gap = value - previous
            if gap > max_gap:
                max_gap = gap
        previous = value

    return max_gap or 1


def _resolve_target_rssi(base_db: Optional[int]) -> Tuple[int, int, int]:
    applied_db = base_db if base_db is not None else _get_current_attenuation()
    applied_db = _clamp_db(applied_db)
    step = _initial_step_size()
    current_rssi = pytest.dut.get_rssi()
    return current_rssi, applied_db, step


def _step_att_db(applied_db: int, step: int, diff: int, attempt: int, target_rssi: int) -> Tuple[int, bool]:
    direction = 1 if diff > 0 else -1
    next_db = max(0, min(110, applied_db + direction * step))
    if next_db == applied_db:
        return applied_db, False
    logging.info(
        'Adjust attenuation to %s dB (attempt %s) for RSSI diff=%s dB (target %s dBm)',
        next_db,
        attempt + 1,
        diff,
        target_rssi,
    )
    try:
        rf_tool.execute_rf_cmd(next_db)
    except Exception as exc:
        logging.warning('Failed to execute rf command %s: %s', next_db, exc)
        return applied_db, False
    return next_db, True


def _record_adjustment(next_db: int, target_rssi: int) -> Tuple[int, Optional[int]]:
    time.sleep(3)
    measured = pytest.dut.get_rssi()
    if measured == -1:
        return measured, None
    new_diff = measured - target_rssi
    logging.info(
        'Measured RSSI %s dBm (diff %s dB) after attenuation %s dB',
        measured,
        new_diff,
        next_db,
    )
    return measured, new_diff


def _adjust_rssi_to_target(target_rssi: int, base_db: Optional[int]) -> Tuple[int, Optional[int]]:
    flags = get_debug_flags()
    if flags.skip_corner_rf:
        simulated_rssi = pytest.dut.get_rssi()
        reason = describe_debug_reason("skip_corner_rf", database_mode=flags.database_mode)
        logging.info(
            "Debug flag (%s) enabled, skip RSSI adjustment and return simulated RSSI %s dBm",
            reason,
            simulated_rssi,
        )
        return simulated_rssi, _clamp_db(base_db if base_db is not None else _get_current_attenuation())

    current_rssi, applied_db, step = _resolve_target_rssi(base_db)
    logging.info(
        'Start adjusting attenuation to %s dB for target RSSI %s dBm',
        applied_db,
        target_rssi,
    )
    if current_rssi == -1:
        return current_rssi, applied_db

    max_iterations = 30
    for attempt in range(max_iterations):
        diff = current_rssi - target_rssi
        logging.info('current rssi %s target rssi %s', current_rssi, target_rssi)
        if diff == 0:
            break

        next_db, changed = _step_att_db(applied_db, step, diff, attempt, target_rssi)
        if not changed:
            if step > 1:
                step = 1
                continue
            logging.info(
                'Attenuation locked at %s dB while RSSI diff=%s dB; boundary reached.',
                applied_db,
                diff,
            )
            break

        measured, new_diff = _record_adjustment(next_db, target_rssi)
        applied_db = next_db
        current_rssi = measured

        if measured == -1:
            break
        if new_diff == 0:
            break

        if new_diff is not None:
            if abs(new_diff) >= abs(diff) and step > 1:
                step = max(1, step // 2)
            elif step > 1 and abs(new_diff) <= 1:
                step = 1

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
            'Both %s.%s %s and %s.%s %s detected; '
            'only one group is supported. Target RSSI values take precedence.',
            TURN_TABLE_SECTION_KEY,
            TURN_TABLE_FIELD_STATIC_DB,
            static_values,
            TURN_TABLE_SECTION_KEY,
            TURN_TABLE_FIELD_TARGET_RSSI,
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
    flags = get_debug_flags()
    if flags.skip_corner_rf:
        reason = describe_debug_reason("skip_corner_rf", database_mode=flags.database_mode)
        logging.info(
            'Debug flag (%s) enabled, skip applying static attenuation %s dB.',
            reason,
            static_db,
        )
        measured = pytest.dut.get_rssi()
        return measured, static_db
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
    corner_tool.set_turntable_zero()

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
    test_result = ensure_performance_result()
    with scenario_group(router_info):
        test_result.ensure_log_file_prefix("RVO")
        if not connect_status:
            logging.info("Can't connect wifi ,input 0")
            return

        logging.info('RVO profile %s', _profile_id(profile))
        logging.info('corner angle set to %s', corner_angle)
        logging.info('start test iperf tx %s rx %s', router_info.tx, router_info.rx)

        test_result.set_active_profile(profile.mode, profile.value)
        try:
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
        finally:
            test_result.clear_active_profile()

    performance_sync_manager(
        "RVO",
        test_result.log_file,
        message="RVO data rows stored in database",
    )
