#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""RVO performance test flow with streamlined fixture handling."""

import logging
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
from src.test import (
    adjust_rssi_to_target,
    common_setup,
    describe_debug_reason,
    ensure_performance_result,
    get_corner_step_list,
    get_rvo_static_db_list,
    get_rvo_target_rssi_list,
    init_corner,
    init_rf,
    init_router,
    scenario_group,
    wait_connect,
)


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
        reason = describe_debug_reason("skip_corner_rf")
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
        return adjust_rssi_to_target(rf_tool, profile.value, None)
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
        message="RVO data stored",
    )
