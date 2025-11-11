"""Demo stress test placeholder for test_str.py."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional

import pytest

from src.test.stability import (
    STABILITY_COMPLETED_LOOPS_ENV,
    STABILITY_LOOPS_ENV,
    extract_checkpoints,
    extract_stability_case,
    load_stability_plan,
)
from src.tools.config_loader import load_config
from src.tools.usb_relay_controller import UsbRelayDevice, pulse


@dataclass(frozen=True)
class CycleConfig:
    """Relay toggle cycle configuration."""

    enabled: bool
    on_duration: int
    off_duration: int
    port: str
    mode: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "CycleConfig":
        data = data or {}

        def _coerce_duration(raw: Any) -> int:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return 0
            return max(0, value)

        return cls(
            enabled=bool(data.get("enabled")),
            on_duration=_coerce_duration(data.get("on_duration")),
            off_duration=_coerce_duration(data.get("off_duration")),
            port=str(data.get("port", "") or "").strip(),
            mode=str(data.get("mode", "") or "NO").strip().upper() or "NO",
        )


@dataclass(frozen=True)
class TestStrSettings:
    """Consolidated STR stability settings."""

    ac: CycleConfig
    str_cycle: CycleConfig

    @property
    def has_work(self) -> bool:
        return self.ac.enabled or self.str_cycle.enabled


def _load_case_settings(case_name: str) -> tuple[TestStrSettings, Mapping[str, bool]]:
    config = load_config(refresh=True)
    stability_cfg = config.get("stability") if isinstance(config, Mapping) else {}
    case_cfg = extract_stability_case(stability_cfg, case_name)
    settings = TestStrSettings(
        ac=CycleConfig.from_mapping(case_cfg.get("ac")),
        str_cycle=CycleConfig.from_mapping(case_cfg.get("str")),
    )
    checkpoints = extract_checkpoints(stability_cfg)
    return settings, checkpoints


def _resolve_loop_budget(plan) -> tuple[Optional[int], Optional[float]]:
    loops: Optional[int]
    if plan.mode == "loops":
        loops = max(1, plan.loops or 1)
    else:
        loops = None

    raw_override = os.environ.get(STABILITY_LOOPS_ENV)
    if raw_override is not None:
        try:
            override = int(raw_override)
        except (TypeError, ValueError):
            override = None
        if override is not None and override > 0:
            loops = override

    deadline: Optional[float] = None
    if plan.mode == "duration" and plan.duration_hours:
        deadline = time.monotonic() + plan.duration_hours * 3600
    return loops, deadline


def _log_loop_start(iteration: int, plan_mode: str, loops: Optional[int], has_deadline: bool) -> None:
    if loops is not None:
        logging.info("[STR] stability loop %s/%s start", iteration, loops)
    elif plan_mode == "duration" and has_deadline:
        logging.info("[STR] stability loop %s start (duration mode)", iteration)
    elif plan_mode == "limit":
        logging.info("[STR] stability loop %s start (limit mode)", iteration)


def _log_loop_end(iteration: int, plan_mode: str, loops: Optional[int], has_deadline: bool) -> None:
    if loops is not None:
        logging.info("[STR] stability loop %s/%s complete", iteration, loops)
    elif plan_mode == "duration" and has_deadline:
        logging.info("[STR] stability loop %s complete (duration mode)", iteration)
    elif plan_mode == "limit":
        logging.info("[STR] stability loop %s complete (limit mode)", iteration)


def _should_continue(iteration: int, loops: Optional[int], deadline: Optional[float]) -> bool:
    if loops is not None and iteration >= loops:
        return False
    if deadline is not None and iteration > 0 and time.monotonic() >= deadline:
        return False
    return True


def execute_ac_cycle(cycle: CycleConfig) -> None:
    _run_cycle("AC", cycle)


def execute_str_cycle(cycle: CycleConfig) -> None:
    _run_cycle("STR", cycle)


def perform_ping_check(label: str) -> None:
    logging.info("[%s] Ping verification placeholder: implement connectivity check", label)


def run_check_points(label: str, checkpoints: Mapping[str, bool]) -> None:
    if checkpoints.get("ping"):
        perform_ping_check(label)


def _run_cycle(label: str, cycle: CycleConfig) -> None:
    if not cycle.enabled:
        logging.info("[%s] cycle disabled; skipping", label)
        return
    if not cycle.port:
        logging.warning("[%s] relay port not configured; skipping", label)
        return
    logging.info(
        "[%s] cycle start: on=%ss off=%ss mode=%s port=%s",
        label,
        cycle.on_duration,
        cycle.off_duration,
        cycle.mode,
        cycle.port,
    )
    try:
        with UsbRelayDevice(cycle.port) as relay:
            if cycle.on_duration > 0:
                time.sleep(cycle.on_duration)
            pulse(relay, cycle.mode)
            if cycle.off_duration > 0:
                time.sleep(cycle.off_duration)
            pulse(relay, cycle.mode)
    except Exception as exc:  # pragma: no cover - hardware dependent
        logging.error("[%s] relay operation failed: %s", label, exc)
        return


def test_str_workflow() -> None:
    plan = load_stability_plan()
    loops, deadline = _resolve_loop_budget(plan)

    os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"

    settings, checkpoints = _load_case_settings("test_str")
    if not settings.has_work:
        os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"
        pytest.skip("AC and STR cycles are both disabled; nothing to execute.")

    completed_loops = 0
    try:
        iteration = 0
        while True:
            if not _should_continue(iteration, loops, deadline):
                break

            iteration += 1
            _log_loop_start(iteration, plan.mode, loops, deadline is not None)

            if settings.ac.enabled:
                execute_ac_cycle(settings.ac)
                run_check_points("AC", checkpoints)
            if settings.str_cycle.enabled:
                execute_str_cycle(settings.str_cycle)
                run_check_points("STR", checkpoints)
            completed_loops += 1
            os.environ[STABILITY_COMPLETED_LOOPS_ENV] = str(completed_loops)

            _log_loop_end(iteration, plan.mode, loops, deadline is not None)

            if deadline is not None and time.monotonic() >= deadline:
                break
    finally:
        os.environ[STABILITY_COMPLETED_LOOPS_ENV] = str(completed_loops)
