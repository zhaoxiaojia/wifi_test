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
    STABILITY_LOOPS_ENV,
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


def _extract_stability_case(
    stability_cfg: Mapping[str, Any] | None, case_name: str
) -> Mapping[str, Any]:
    if not isinstance(stability_cfg, Mapping):
        return {}
    cases_section = stability_cfg.get("cases")
    if not isinstance(cases_section, Mapping):
        return {}
    entry = cases_section.get(case_name)
    return entry if isinstance(entry, Mapping) else {}


def _extract_checkpoints(stability_cfg: Mapping[str, Any] | None) -> Mapping[str, bool]:
    if not isinstance(stability_cfg, Mapping):
        return {}
    checkpoints = stability_cfg.get("check_point")
    if not isinstance(checkpoints, Mapping):
        return {}
    return {key: bool(value) for key, value in checkpoints.items()}


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
            pulse(relay, cycle.mode)
            if cycle.on_duration > 0:
                time.sleep(cycle.on_duration)
            pulse(relay, cycle.mode)
            if cycle.off_duration > 0:
                time.sleep(cycle.off_duration)
    except Exception as exc:  # pragma: no cover - hardware dependent
        logging.error("[%s] relay operation failed: %s", label, exc)
        return


def test_str_workflow() -> None:
    plan = load_stability_plan()
    loops = plan.loops if plan.mode == "loops" else 1
    try:
        requested_loops = int(os.environ.get(STABILITY_LOOPS_ENV, loops))
    except (TypeError, ValueError):
        requested_loops = loops
    if requested_loops > 0:
        loops = requested_loops
    loops = max(1, loops)
    os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"

    config = load_config(refresh=True)
    stability_cfg = config.get("stability") if isinstance(config, Mapping) else {}
    case_cfg = _extract_stability_case(stability_cfg, "test_str")
    settings = TestStrSettings(
        ac=CycleConfig.from_mapping(case_cfg.get("ac")),
        str_cycle=CycleConfig.from_mapping(case_cfg.get("str")),
    )
    if not settings.has_work:
        os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"
        pytest.skip("AC and STR cycles are both disabled; nothing to execute.")

    checkpoints = _extract_checkpoints(stability_cfg)
    completed_loops = 0
    try:
        for iteration in range(1, loops + 1):
            if loops > 1:
                logging.info("[STR] stability loop %s/%s start", iteration, loops)
            if settings.ac.enabled:
                execute_ac_cycle(settings.ac)
                run_check_points("AC", checkpoints)
            if settings.str_cycle.enabled:
                execute_str_cycle(settings.str_cycle)
                run_check_points("STR", checkpoints)
            completed_loops += 1
            if loops > 1:
                logging.info("[STR] stability loop %s/%s complete", iteration, loops)
    finally:
        os.environ[STABILITY_COMPLETED_LOOPS_ENV] = str(completed_loops)
