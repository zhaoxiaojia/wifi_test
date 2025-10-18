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
    """Adapt attenuation until the measured RSSI matches ``target_rssi``.

    The relationship between the RF attenuation value (in dB) and the received
    signal strength is logarithmic. In a log scale an increment of ``x`` dB on
    the attenuator translates to roughly ``x`` dBm of additional path loss.
    Leveraging this property allows us to jump directly towards the expected
    attenuation and then refine the value with a binary search, which keeps the
    number of adjustments minimal while still converging exactly to the target
    RSSI when possible.
    """

    def _clamp_db(value: int) -> int:
        return max(0, min(110, int(value)))

    def _apply_and_measure(db_value: int, attempt: int, last_rssi: int) -> Optional[int]:
        logging.info(
            'Adjust attenuation to %s dB (attempt %s) for RSSI %s dBm -> target %s dBm',
            db_value,
            attempt,
            last_rssi,
            target_rssi,
        )
        try:
            rf_tool.execute_rf_cmd(db_value)
        except Exception as exc:
            logging.warning('Failed to execute rf command %s: %s', db_value, exc)
            return None
        time.sleep(3)
        return pytest.dut.get_rssi()

    max_iterations = 24
    applied_db = base_db if base_db is not None else _get_current_attenuation()
    applied_db = _clamp_db(applied_db)
    logging.info(
        'Start adjusting attenuation to %s dB for target RSSI %s dBm',
        applied_db,
        target_rssi,
    )

    current_rssi = pytest.dut.get_rssi()
    if current_rssi == -1:
        return current_rssi, applied_db

    measurements: dict[int, int] = {applied_db: current_rssi}
    visited: set[int] = {applied_db}

    low_db: Optional[int] = None
    low_rssi: Optional[int] = None
    high_db: Optional[int] = None
    high_rssi: Optional[int] = None

    def _record_bound(db_value: int, measured_rssi: int) -> None:
        nonlocal low_db, low_rssi, high_db, high_rssi
        if measured_rssi < target_rssi:
            if low_db is None or db_value > low_db:
                low_db = db_value
                low_rssi = measured_rssi
        elif measured_rssi > target_rssi:
            if high_db is None or db_value < high_db:
                high_db = db_value
                high_rssi = measured_rssi

    _record_bound(applied_db, current_rssi)

    for attempt in range(1, max_iterations + 1):
        logging.info('current rssi %s target rssi %s', current_rssi, target_rssi)
        if current_rssi == target_rssi:
            break

        delta = target_rssi - current_rssi
        next_db: Optional[int] = None

        if low_db is not None and high_db is not None and low_db < high_db:
            if high_db - low_db <= 1:
                candidates = [
                    (abs(low_rssi - target_rssi) if low_rssi is not None else float('inf'), low_db),
                    (abs(high_rssi - target_rssi) if high_rssi is not None else float('inf'), high_db),
                ]
                candidates.sort()
                for _, candidate_db in candidates:
                    if candidate_db != applied_db and candidate_db not in visited:
                        next_db = candidate_db
                        break
                if next_db is None:
                    # All nearby candidates already inspected; nothing better to try.
                    break
            else:
                midpoint = _clamp_db(round((low_db + high_db) / 2))
                if midpoint != applied_db:
                    next_db = midpoint
                else:
                    step = 1 if delta > 0 else -1
                    candidate = _clamp_db(applied_db + step)
                    if candidate != applied_db:
                        next_db = candidate
        else:
            estimated = _clamp_db(applied_db + delta)
            if estimated != applied_db:
                next_db = estimated
            else:
                step = 1 if delta > 0 else -1
                candidate = _clamp_db(applied_db + step)
                if candidate != applied_db:
                    next_db = candidate

        if next_db is None or next_db == applied_db:
            break
        if next_db in visited:
            step = 1 if delta > 0 else -1
            alternative = _clamp_db(next_db + step)
            if alternative == next_db or alternative in visited:
                break
            next_db = alternative

        new_rssi = _apply_and_measure(next_db, attempt, current_rssi)
        if new_rssi is None:
            break
        applied_db = next_db
        current_rssi = new_rssi
        if current_rssi == -1:
            break

        measurements[applied_db] = current_rssi
        visited.add(applied_db)
        _record_bound(applied_db, current_rssi)

    if current_rssi != target_rssi and current_rssi != -1:
        fine_attempt = 0
        while fine_attempt < 6 and current_rssi != target_rssi:
            delta = target_rssi - current_rssi
            if delta == 0:
                break
            step = 1 if delta > 0 else -1
            candidate = _clamp_db(applied_db + step)
            if candidate == applied_db:
                break
            new_rssi = _apply_and_measure(candidate, max_iterations + 1 + fine_attempt, current_rssi)
            if new_rssi is None:
                break
            applied_db = candidate
            current_rssi = new_rssi
            if current_rssi == -1:
                break
            measurements[applied_db] = current_rssi
            visited.add(applied_db)
            _record_bound(applied_db, current_rssi)
            fine_attempt += 1

    if current_rssi != target_rssi and measurements:
        exact_db_candidates = [db for db, rssi in measurements.items() if rssi == target_rssi]
        if exact_db_candidates:
            desired_db = min(exact_db_candidates, key=lambda db: abs(db - applied_db))
            if desired_db != applied_db:
                final_rssi = _apply_and_measure(desired_db, max_iterations + 7, current_rssi)
                if final_rssi is not None and final_rssi != -1:
                    applied_db = desired_db
                    current_rssi = final_rssi
                    measurements[applied_db] = current_rssi
        else:
            best_db, best_rssi = min(
                measurements.items(),
                key=lambda item: (abs(item[1] - target_rssi), item[0]),
            )
            if best_db != applied_db:
                final_rssi = _apply_and_measure(best_db, max_iterations + 7, current_rssi)
                if final_rssi is not None and final_rssi != -1:
                    applied_db = best_db
                    current_rssi = final_rssi
                    measurements[applied_db] = current_rssi

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
