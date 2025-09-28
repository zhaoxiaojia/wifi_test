# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
File       : test_wifi_rvr.py
Time       ：2023/9/15 14:03
Author     ：chao.li
version    ：python 3.9
Description：
"""

import logging
from typing import Optional

from src.test import get_testdata
from src.test.pyqt_log import log_fixture_params, update_fixture_params
import pytest

from src.test.performance import (
    common_setup,
    get_cfg,
    get_rf_step_list,
    init_rf,
    init_router,
)

_test_data = get_testdata(init_router())
rf_tool = init_rf()


@pytest.fixture(scope='session', params=_test_data, ids=[str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    _attenuation_scheduler.reset()
    router_info = request.param
    router = init_router()
    connect_status = common_setup(router, router_info)
    yield connect_status, router_info
    pytest.dut.kill_iperf()


DEFAULT_STEP = 3
REDUCED_STEP = 2
RSSI_THRESHOLD = 65


class AttenuationScheduler:
    def __init__(self) -> None:
        self._last_applied: Optional[int] = None
        self._current_step = DEFAULT_STEP
        self._max_db = self._compute_max_db()

    def reset(self) -> None:
        """重置内部状态，确保新的路由/信道组合从 0 dB 开始。"""
        self._last_applied = None
        self._current_step = DEFAULT_STEP
        self._max_db = self._compute_max_db()

    @staticmethod
    def _compute_max_db() -> int:
        steps = get_rf_step_list()
        max_from_steps = steps[-1] if steps else 0
        try:
            cfg = get_cfg()
            configured_max = cfg['rf_solution']['step'][1]
            max_from_steps = max(max_from_steps, int(configured_max))
        except (KeyError, TypeError, ValueError, IndexError):
            pass
        return max_from_steps

    @property
    def current_step(self) -> int:
        return self._current_step

    def next_value(self, base_db: int) -> int:
        target = min(base_db, self._max_db)

        if self._last_applied is None:
            applied = target
        else:
            candidate = min(self._last_applied + self._current_step, self._max_db)
            if self._current_step < DEFAULT_STEP and candidate < target:
                applied = candidate
            else:
                applied = max(target, candidate)

        if self._last_applied is not None and applied < self._last_applied:
            applied = self._last_applied

        if applied != target:
            logging.info(
                '根据动态步进策略，将衰减值从计划值 %s 调整为 %s（当前步进 %s dB）',
                target,
                applied,
                self._current_step,
            )

        self._last_applied = applied

        if applied >= self._max_db and target < self._max_db:
            logging.info('衰减达到上限 %s dB，后续将维持此值', self._max_db)

        return applied

    def record_rssi(self, rssi_value: Optional[float]) -> None:
        if rssi_value is None:
            return
        try:
            numeric_rssi = float(rssi_value)
        except (TypeError, ValueError):
            numeric_rssi = None

        if numeric_rssi is not None and numeric_rssi > RSSI_THRESHOLD:
            self._activate_reduced_mode(numeric_rssi)
        else:
            self._deactivate_reduced_mode(numeric_rssi)

    def _activate_reduced_mode(self, current_rssi: float) -> None:
        if self._current_step == REDUCED_STEP:
            return
        logging.info(
            'RSSI %.2f 超过阈值 %s，衰减步进从 %s dB 调整为 %s dB',
            current_rssi,
            RSSI_THRESHOLD,
            DEFAULT_STEP,
            REDUCED_STEP,
        )
        self._current_step = REDUCED_STEP

    def _deactivate_reduced_mode(self, current_rssi: Optional[float]) -> None:
        if self._current_step != DEFAULT_STEP:
            logging.info(
                'RSSI %s 低于或等于阈值 %s，恢复默认 %s dB 步进',
                current_rssi,
                RSSI_THRESHOLD,
                DEFAULT_STEP,
            )
        self._current_step = DEFAULT_STEP


_attenuation_scheduler = AttenuationScheduler()


@pytest.fixture(scope='function', params=get_rf_step_list())
@log_fixture_params()
def setup_attenuation(request, setup_router):
    db_set = request.param
    connect_status, router_info = setup_router

    applied_db = _attenuation_scheduler.next_value(db_set)

    update_fixture_params(
        request,
        {
            'requested': db_set,
            'applied': applied_db,
            'step': _attenuation_scheduler.current_step,
        },
    )

    rf_tool.execute_rf_cmd(applied_db)
    logging.info('设置衰减：请求 %s dB，实际 %s dB', db_set, applied_db)
    logging.info(rf_tool.get_rf_current_value())

    pytest.dut.get_rssi()
    _attenuation_scheduler.record_rssi(pytest.dut.rssi_num)

    yield (connect_status, router_info, applied_db)
    pytest.dut.kill_iperf()


def test_rvr(setup_attenuation):
    connect_status, router_info, db_set = setup_attenuation
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        return

    logging.info(f'start test iperf tx {router_info.tx} rx {router_info.rx}')

    if int(router_info.tx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_tx_rate(router_info, 'TCP', db_set=db_set)
    if int(router_info.rx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_rx_rate(router_info, 'TCP', db_set=db_set)
