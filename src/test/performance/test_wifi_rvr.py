# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
File       : test_wifi_rvr.py
Time       : 2023/9/15 14:03
Author     : chao.li
version    : python 3.9
Description:
"""

import heapq
import logging
import time
from collections import Counter
from dataclasses import dataclass
from typing import Iterator, Optional

import pytest

from src.test import get_testdata
from src.test.pyqt_log import log_fixture_params, update_fixture_params
from src.test.performance import (
    common_setup,
    get_cfg,
    get_rf_step_list,
    init_rf,
    init_router,
)
from src.tools.router_tool.Router import router_str


_test_data = get_testdata(init_router())
rf_tool = init_rf()

DEFAULT_STEP = 3
REDUCED_STEP = 2
RSSI_THRESHOLD = 65


def _safe_float(value: object) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class AttenuationStepResult:
    iteration: int
    requested_db: int
    applied_db: int
    step_db: int
    rssi: Optional[float]


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

    @property
    def max_db(self) -> int:
        return self._max_db

    def next_value(self, base_db: int) -> int:
        target = min(base_db, self._max_db)

        if self._last_applied is None:
            applied = target
        else:
            candidate = min(self._last_applied + self._current_step, self._max_db)
            if candidate < target:
                applied = candidate
                logging.info(
                    'Dynamic step: planned %s dB, executing %s dB first (step %s dB)',
                    target,
                    applied,
                    self._current_step,
                )
            else:
                applied = target

        if self._last_applied is not None and applied < self._last_applied:
            applied = self._last_applied

        if applied > target:
            applied = target

        if applied != target:
            logging.info(
                'Adjusted attenuation from planned %s dB to %s dB (step %s dB)',
                target,
                applied,
                self._current_step,
            )

        self._last_applied = applied

        if applied >= self._max_db and target < self._max_db:
            logging.info('The attenuation has reached the upper limit of %s dB and will remain at this value subsequently.', self._max_db)

        return applied

    def record_rssi(self, rssi_value: Optional[float]) -> None:
        if rssi_value is None:
            return
        numeric_rssi = _safe_float(rssi_value)
        if numeric_rssi is None:
            return
        if numeric_rssi > RSSI_THRESHOLD:
            self._activate_reduced_mode(numeric_rssi)
        else:
            self._deactivate_reduced_mode(numeric_rssi)

    def _activate_reduced_mode(self, current_rssi: float) -> None:
        if self._current_step == REDUCED_STEP:
            return
        logging.info(
            'RSSI %.2f exceeds the threshold %s, and the attenuation step is adjusted from %s dB to %s dB.',
            current_rssi,
            RSSI_THRESHOLD,
            DEFAULT_STEP,
            REDUCED_STEP,
        )
        self._current_step = REDUCED_STEP

    def _deactivate_reduced_mode(self, current_rssi: Optional[float]) -> None:
        if self._current_step != DEFAULT_STEP:
            logging.info(
                'The RSSI %s is lower than or equal to the threshold %s. It will revert to the default %s dB increment.',
                current_rssi,
                RSSI_THRESHOLD,
                DEFAULT_STEP,
            )
        self._current_step = DEFAULT_STEP


_attenuation_scheduler = AttenuationScheduler()


class AttenuationRunner(Iterator[AttenuationStepResult]):
    def __init__(
        self,
        request,
        connect_status: bool,
        router_info,
        scheduler: AttenuationScheduler,
        rf_controller,
        planned_steps,
    ) -> None:
        self.connect_status = connect_status
        self.router_info = router_info
        self._request = request
        self._scheduler = scheduler
        self._rf_tool = rf_controller
        self._iteration = 0
        self._max_db = self._scheduler.max_db
        self._pending_heap: list[int] = []
        self._pending_counts: Counter[int] = Counter()
        self._processed: set[int] = set()

        unique_steps = sorted({int(value) for value in planned_steps})
        if not unique_steps:
            unique_steps = [0]
        for value in unique_steps:
            self._enqueue(value)

    def __iter__(self) -> 'AttenuationRunner':
        return self

    def __next__(self) -> AttenuationStepResult:
        while True:
            if not self._pending_counts:
                raise StopIteration
            requested = self._pop_next()
            if requested in self._processed:
                continue

            prev_step = self._scheduler.current_step
            applied = int(self._scheduler.next_value(requested))
            self._iteration += 1

            if applied < requested:
                logging.info(
                    'Dynamic coverage: planned %s dB, executing %s dB first (step %s dB)',
                    requested,
                    applied,
                    prev_step,
                )

            self._rf_tool.execute_rf_cmd(applied)
            logging.info(
                'Set attenuation: requested %s dB, applied %s dB',
                requested,
                applied,
            )
            logging.info(self._rf_tool.get_rf_current_value())

            pytest.dut.get_rssi()
            current_rssi_raw = pytest.dut.rssi_num
            current_rssi = _safe_float(current_rssi_raw)
            self._scheduler.record_rssi(current_rssi_raw)

            new_step = self._scheduler.current_step

            if applied < requested:
                self._enqueue(requested)
            self._processed.add(applied)

            if new_step != prev_step or applied < requested:
                self._schedule_from(applied, new_step)

            params = {
                'iteration': self._iteration,
                'requested': requested,
                'applied': applied,
                'step': new_step,
            }
            if new_step != prev_step:
                params['prev_step'] = prev_step
            if current_rssi is not None:
                params['rssi'] = current_rssi

            update_fixture_params(self._request, params)

            return AttenuationStepResult(
                iteration=self._iteration,
                requested_db=requested,
                applied_db=applied,
                step_db=new_step,
                rssi=current_rssi,
            )

    def _enqueue(self, value: int) -> None:
        if value > self._max_db:
            return
        heapq.heappush(self._pending_heap, value)
        self._pending_counts[value] += 1

    def _pop_next(self) -> int:
        while self._pending_heap:
            value = heapq.heappop(self._pending_heap)
            count = self._pending_counts.get(value, 0)
            if count == 0:
                continue
            if count == 1:
                del self._pending_counts[value]
            else:
                self._pending_counts[value] = count - 1
            return value
        raise StopIteration

    def _is_pending(self, value: int) -> bool:
        return self._pending_counts.get(value, 0) > 0

    def _schedule_from(self, start: int, step: int) -> None:
        if step <= 0:
            return
        candidate = start + step
        while candidate <= self._max_db:
            if candidate not in self._processed and not self._is_pending(candidate):
                self._enqueue(candidate)
            candidate += step


@pytest.fixture(scope='session', params=_test_data, ids=[router_str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    _attenuation_scheduler.reset()
    router_info = request.param
    logging.info('Reset rf value before router setup')
    rf_tool.execute_rf_cmd(0)
    logging.info(rf_tool.get_rf_current_value())
    time.sleep(3)
    router = init_router()
    connect_status = common_setup(router, router_info)
    yield connect_status, router_info
    pytest.dut.kill_iperf()
    time.sleep(3)


@pytest.fixture(scope='function')
@log_fixture_params()
def setup_attenuation(request, setup_router):
    connect_status, router_info = setup_router
    planned_steps = get_rf_step_list()
    runner = AttenuationRunner(
        request=request,
        connect_status=connect_status,
        router_info=router_info,
        scheduler=_attenuation_scheduler,
        rf_controller=rf_tool,
        planned_steps=planned_steps,
    )
    try:
        yield runner
    finally:
        pytest.dut.kill_iperf()


def test_rvr(setup_attenuation):
    runner = setup_attenuation
    if not runner.connect_status:
        logging.info("Can't connect wifi ,input 0")
        return

    logging.info(
        'start test iperf tx %s rx %s',
        runner.router_info.tx,
        runner.router_info.rx,
    )

    for step in runner:
        rssi_display = step.rssi if step.rssi is not None else pytest.dut.rssi_num
        logging.info(
            'attenuation iteration %s: requested %s dB, applied %s dB (step %s dB, rssi %s)',
            step.iteration,
            step.requested_db,
            step.applied_db,
            step.step_db,
            rssi_display,
        )

        if int(runner.router_info.tx):
            logging.info('rssi : %s', rssi_display)
            pytest.dut.get_tx_rate(runner.router_info, 'TCP', db_set=step.applied_db)
        if int(runner.router_info.rx):
            logging.info('rssi : %s', rssi_display)
            pytest.dut.get_rx_rate(runner.router_info, 'TCP', db_set=step.applied_db)

        pytest.dut.kill_iperf()
