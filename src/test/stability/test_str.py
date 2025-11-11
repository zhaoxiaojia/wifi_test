"""Demo stress test placeholder for test_str.py."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping

import pytest

from src.test.stability import (
    STABILITY_COMPLETED_LOOPS_ENV,
    describe_iteration,
    extract_checkpoints,
    extract_stability_case,
    iterate_stability_loops,
    load_stability_plan,
    run_checkpoints,
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


def execute_ac_cycle(cycle: CycleConfig) -> None:
    _run_cycle("AC", cycle)


def execute_str_cycle(cycle: CycleConfig) -> None:
    _run_cycle("STR", cycle)


def perform_ping_check(label: str) -> None:
    logging.info("[%s] Ping verification placeholder: implement connectivity check", label)


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

    os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"

    settings, checkpoints = _load_case_settings("test_str")
    if not settings.has_work:
        os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"
        pytest.skip("AC and STR cycles are both disabled; nothing to execute.")

    for iteration, budget, report_completion in iterate_stability_loops(plan):
        iteration_label = describe_iteration(iteration, budget, plan.mode)
        logging.info("[STR] stability %s start", iteration_label)

        if settings.ac.enabled:
            execute_ac_cycle(settings.ac)
            run_checkpoints("AC", checkpoints, ping_cb=perform_ping_check)
        if settings.str_cycle.enabled:
            execute_str_cycle(settings.str_cycle)
            run_checkpoints("STR", checkpoints, ping_cb=perform_ping_check)

        report_completion()
        logging.info("[STR] stability %s complete", iteration_label)
