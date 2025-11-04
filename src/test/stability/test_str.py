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
from src.tools.usb_relay_controller import (
    UsbRelayDevice,
    apply_state,
)

def _script_case_key(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized.replace("/", "__").replace(".", "_").lower()


SCRIPT_RELATIVE_PATH = "test/stability/test_str.py"
_SCRIPT_CONFIG_KEY = _script_case_key(SCRIPT_RELATIVE_PATH)


@dataclass(frozen=True)
class CycleConfig:
    enabled: bool
    on_duration: int
    off_duration: int
    ping: bool
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
            ping=bool(data.get("ping")),
            port=str(data.get("port", "") or "").strip(),
            mode=str(data.get("mode", "") or "NO").strip().upper() or "NO",
        )


@dataclass(frozen=True)
class TestStrSettings:
    ac: CycleConfig
    str_cycle: CycleConfig

    @property
    def has_work(self) -> bool:
        return self.ac.enabled or self.str_cycle.enabled


def load_test_str_settings(*, refresh: bool = True) -> TestStrSettings:
    config = load_config(refresh=refresh)
    entry: Mapping[str, Any] | None = None
    script_section = config.get("script_params")

    if isinstance(script_section, Mapping):
        entry = script_section.get(_SCRIPT_CONFIG_KEY)
        if not isinstance(entry, Mapping):
            entry = next(
                (
                    value
                    for value in script_section.values()
                    if isinstance(value, Mapping)
                    and value.get("case_path") == SCRIPT_RELATIVE_PATH
                ),
                None,
            )

    entry = entry or {}
    ac_cfg = CycleConfig.from_mapping(entry.get("ac"))
    str_cfg = CycleConfig.from_mapping(entry.get("str"))
    return TestStrSettings(ac=ac_cfg, str_cycle=str_cfg)


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
    logging.info("[%s] cycle start: on=%ss off=%ss mode=%s port=%s", label, cycle.on_duration, cycle.off_duration, cycle.mode, cycle.port)
    try:
        with UsbRelayDevice(cycle.port) as relay:
            apply_state(relay, cycle.mode, "on")
            if cycle.on_duration > 0:
                time.sleep(cycle.on_duration)
            apply_state(relay, cycle.mode, "off")
            if cycle.off_duration > 0:
                time.sleep(cycle.off_duration)
    except Exception as exc:  # pragma: no cover - hardware dependent
        logging.error("[%s] relay operation failed: %s", label, exc)
        return
    if cycle.ping:
        perform_ping_check(label)


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

    settings = load_test_str_settings()
    if not settings.has_work:
        os.environ[STABILITY_COMPLETED_LOOPS_ENV] = "0"
        pytest.skip("AC and STR cycles are both disabled; nothing to execute.")

    completed_loops = 0
    try:
        for iteration in range(1, loops + 1):
            if loops > 1:
                logging.info("[STR] stability loop %s/%s start", iteration, loops)
            if settings.ac.enabled:
                execute_ac_cycle(settings.ac)
            if settings.str_cycle.enabled:
                execute_str_cycle(settings.str_cycle)
            completed_loops += 1
            if loops > 1:
                logging.info("[STR] stability loop %s/%s complete", iteration, loops)
    finally:
        os.environ[STABILITY_COMPLETED_LOOPS_ENV] = str(completed_loops)
