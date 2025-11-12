"""Utilities shared by stability stress test suites."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, Mapping, Optional
import sys
import time

import pytest

from src.util import parse_host_list

__all__ = [
    "StabilityPlan",
    "extract_checkpoints",
    "extract_stability_case",
    "is_stability_case_path",
    "load_stability_plan",
    "prepare_stability_environment",
    "run_stability_plan",
    "run_checkpoints",
    "LoopBudget",
    "iterate_stability_loops",
    "describe_iteration",
    "STABILITY_COMPLETED_LOOPS_ENV",
    "STABILITY_LOOPS_ENV",
    "STABILITY_MODE_ENV",
    "STABILITY_DURATION_ENV",
    "CheckpointConfig",
]


STABILITY_MODE_ENV = "WIFI_STABILITY_MODE"
STABILITY_LOOPS_ENV = "WIFI_STABILITY_LOOPS"
STABILITY_DURATION_ENV = "WIFI_STABILITY_DURATION_HOURS"
STABILITY_COMPLETED_LOOPS_ENV = "WIFI_STABILITY_COMPLETED_LOOPS"


@dataclass(frozen=True)
class StabilityPlan:
    """Normalized stability execution plan."""

    mode: str
    loops: Optional[int]
    duration_hours: Optional[float]
    exit_first: bool = False
    retry_limit: int = 0


@dataclass(frozen=True)
class LoopBudget:
    """Snapshot of the remaining stability execution budget."""

    total_loops: Optional[int]
    remaining_loops: Optional[int]
    remaining_seconds: Optional[int]


@dataclass(frozen=True)
class CheckpointConfig:
    """Normalized checkpoint configuration shared across stability suites."""

    ping_enabled: bool = False
    ping_targets: tuple[str, ...] = ()


def _iter_segments(candidate: Path) -> Iterable[str]:
    """Yield lowercase path segments for ``candidate``."""

    for segment in candidate.as_posix().split("/"):
        segment = segment.strip()
        if segment:
            yield segment.lower()


def is_stability_case_path(path: Any) -> bool:
    """Return True when ``path`` points into the stability test suite.

    Args:
        path: Path-like value describing the test module location.

    Returns:
        bool: True if the path contains a ``test/stability`` segment.
    """

    normalized = str(path or "").replace("\\", "/").strip()
    if not normalized:
        return False

    lowered = normalized.lower()
    if "test/stability/" in lowered:
        return True

    try:
        candidate = Path(path)
    except (TypeError, ValueError):
        return False

    try:
        resolved = candidate.resolve()
    except OSError:
        resolved = candidate

    for probe in (candidate, resolved):
        segments = tuple(_iter_segments(probe))
        for idx in range(len(segments) - 1):
            if segments[idx] == "test" and segments[idx + 1] == "stability":
                return True

    return False


def extract_stability_case(
    stability_cfg: Mapping[str, Any] | None,
    case_name: str,
    *,
    aliases: Iterable[str] | None = None,
) -> Dict[str, Any]:
    """Return normalized stability case configuration."""

    if not isinstance(stability_cfg, Mapping):
        return {}
    cases_section = stability_cfg.get("cases")
    if not isinstance(cases_section, Mapping):
        return {}

    entry = cases_section.get(case_name)
    if isinstance(entry, Mapping):
        return dict(entry)

    if aliases:
        for alias in aliases:
            alias_entry = cases_section.get(alias)
            if isinstance(alias_entry, Mapping):
                return dict(alias_entry)

    return {}


def extract_checkpoints(stability_cfg: Mapping[str, Any] | None) -> CheckpointConfig:
    """Return normalized stability checkpoint configuration."""

    if not isinstance(stability_cfg, Mapping):
        return CheckpointConfig()
    checkpoints = stability_cfg.get("check_point")
    if not isinstance(checkpoints, Mapping):
        return CheckpointConfig()
    ping_enabled = bool(checkpoints.get("ping"))
    ping_targets = parse_host_list(checkpoints.get("ping_targets"))
    return CheckpointConfig(ping_enabled=ping_enabled, ping_targets=ping_targets)


def run_checkpoints(
    label: str,
    checkpoints: CheckpointConfig | Mapping[str, Any] | None,
) -> None:
    """Execute enabled checkpoint verifications for ``label``."""

    config = _coerce_checkpoint_config(checkpoints)
    if config.ping_enabled:
        _execute_ping_checkpoint(label, config.ping_targets)


def _coerce_checkpoint_config(
    checkpoints: CheckpointConfig | Mapping[str, Any] | None,
) -> CheckpointConfig:
    """Return a normalized checkpoint configuration for runtime use."""

    if isinstance(checkpoints, CheckpointConfig):
        return checkpoints
    if isinstance(checkpoints, Mapping):
        return CheckpointConfig(
            ping_enabled=bool(checkpoints.get("ping")),
            ping_targets=parse_host_list(checkpoints.get("ping_targets")),
        )
    return CheckpointConfig()


def _execute_ping_checkpoint(label: str, targets: Iterable[str]) -> None:
    """Assert DUT connectivity for each configured ping target."""

    dut = getattr(pytest, "dut", None)
    if dut is None or not hasattr(dut, "ping"):
        pytest.fail(f"[{label}] Unable to execute ping checkpoint without pytest.dut", pytrace=False)
    target_list = tuple(targets)
    if not target_list:
        pytest.fail(f"[{label}] Ping checkpoint requires at least one target", pytrace=False)

    failures: list[bool] = []
    for target in target_list:
        result = dut.ping(hostname=target)
        failures.append(result)

    if any(not x for x in failures):
        pytest.fail(
            f"[{label}] Ping failures", pytrace=False
        )


def _coerce_positive_int(value: Any) -> Optional[int]:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return None
    return candidate if candidate > 0 else None


def _coerce_positive_float(value: Any) -> Optional[float]:
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        return None
    return candidate if candidate > 0 else None


def normalize_stability_config(raw_value: Any) -> StabilityPlan:
    """Normalize persisted stability plan for safe execution."""

    if isinstance(raw_value, dict):
        normalized: Dict[str, Any] = dict(raw_value)
    else:
        normalized = {}

    loop_value = _coerce_positive_int(normalized.get("loop"))
    duration_value = _coerce_positive_float(normalized.get("duration_hours"))
    exit_first = bool(normalized.get("exitfirst"))
    retry_limit = _coerce_positive_int(normalized.get("retry_limit")) or 0

    if loop_value and duration_value:
        logging.info(
            "Both loop and duration were configured; using loop-based stability plan.",
        )
        duration_value = None

    if loop_value:
        return StabilityPlan("loops", loop_value, None, exit_first=exit_first, retry_limit=retry_limit)
    if duration_value:
        return StabilityPlan("duration", None, duration_value, exit_first=exit_first, retry_limit=retry_limit)
    return StabilityPlan("limit", None, None, exit_first=exit_first, retry_limit=retry_limit)


def load_stability_plan() -> StabilityPlan:
    """Load and normalize the current stability execution plan."""

    from src.tools.config_loader import load_config

    snapshot = load_config(refresh=True) or {}
    stability_cfg = snapshot.get("stability")
    duration_cfg = {}
    if isinstance(stability_cfg, dict):
        duration_cfg = stability_cfg.get("duration_control") or {}
    return normalize_stability_config(duration_cfg)


def iterate_stability_loops(plan: StabilityPlan) -> Iterator[tuple[int, LoopBudget, Callable[[bool], None]]]:
    """Yield iteration index, budget snapshot, and completion reporter."""

    loops = plan.loops if plan.mode == "loops" else None
    loops = _coerce_positive_int(loops)
    if loops is not None:
        loops = max(1, loops)

    override = _coerce_positive_int(os.environ.get(STABILITY_LOOPS_ENV))
    if override is not None:
        loops = override

    deadline = None
    if plan.mode == "duration" and plan.duration_hours:
        deadline = time.monotonic() + plan.duration_hours * 3600

    completed = _coerce_positive_int(os.environ.get(STABILITY_COMPLETED_LOOPS_ENV)) or 0
    os.environ[STABILITY_COMPLETED_LOOPS_ENV] = str(completed)

    iteration = 0
    try:
        while True:
            if loops is not None and iteration >= loops:
                break
            if deadline is not None and iteration > 0 and time.monotonic() >= deadline:
                break

            iteration += 1
            current_iteration = iteration
            budget = LoopBudget(
                total_loops=loops,
                remaining_loops=(max(loops - current_iteration, 0) if loops is not None else None),
                remaining_seconds=(
                    max(int(deadline - time.monotonic()), 0)
                    if deadline is not None
                    else None
                ),
            )

            reported = False

            def _report(success: bool = True) -> None:
                nonlocal completed, reported
                if reported:
                    return
                if success:
                    completed = max(completed, current_iteration)
                reported = True
                os.environ[STABILITY_COMPLETED_LOOPS_ENV] = str(completed)

            yield current_iteration, budget, _report
    finally:
        os.environ[STABILITY_COMPLETED_LOOPS_ENV] = str(completed)


def describe_iteration(iteration: int, budget: LoopBudget, mode: str) -> str:
    """Return human-friendly stability loop label."""

    if budget.total_loops is not None:
        return f"loop {iteration}/{budget.total_loops}"
    if mode == "duration" and budget.remaining_seconds is not None:
        return f"loop {iteration} (duration mode)"
    if mode == "limit":
        return f"loop {iteration} (limit mode)"
    return f"loop {iteration}"


def prepare_stability_environment() -> None:
    """Reload configuration and clear cached test modules before execution."""

    from src.tools.config_loader import load_config

    load_config(refresh=True)
    for module_name in list(sys.modules):
        if module_name.startswith("src.test"):
            sys.modules.pop(module_name, None)
    sys.modules.pop("src.tools.config_loader", None)
    sys.modules.pop("src.conftest", None)


def run_stability_plan(
    plan: StabilityPlan,
    *,
    run_pytest: Callable[[], int],
    prepare_env: Optional[Callable[[], None]],
    emit_event: Callable[[str, Dict[str, Any]], None],
    progress_cb: Optional[Callable[[int], None]] = None,
) -> Dict[str, Any]:
    """Execute ``pytest`` under the provided stability plan."""

    delegate_loops = plan.mode == "loops"
    delegate_limit = plan.mode == "limit"
    requested_loops = plan.loops or 0
    total_runs = 0
    passed_runs = 0
    last_exit_code = 0
    stop_reason = ""
    overall_start = time.monotonic()
    deadline = (
        overall_start + plan.duration_hours * 3600
        if plan.mode == "duration" and plan.duration_hours is not None
        else None
    )
    loop_completed = 0

    if plan.mode == "duration" and plan.duration_hours is not None:
        duration_value = f"{plan.duration_hours}"
    elif plan.mode == "limit":
        duration_value = "limit"
    else:
        duration_value = ""

    env_updates: Dict[str, str] = {
        STABILITY_MODE_ENV: plan.mode,
        STABILITY_DURATION_ENV: duration_value,
        STABILITY_COMPLETED_LOOPS_ENV: "0",
    }
    if delegate_loops:
        env_updates[STABILITY_LOOPS_ENV] = str(plan.loops or 0)

    _sentinel = object()
    previous_env: Dict[str, Any] = {}
    for key, value in env_updates.items():
        previous_env[key] = os.environ.get(key, _sentinel)
        os.environ[key] = value
    try:
        emit_event("plan_started", {"plan": plan})

        while True:
            next_iteration = total_runs + 1
            if delegate_loops and total_runs >= 1:
                stop_reason = "completed requested loops"
                break
            if delegate_limit and total_runs >= 1:
                stop_reason = "running until stopped"
                break
            if (
                plan.mode == "duration"
                and total_runs > 0
                and deadline is not None
                and time.monotonic() >= deadline
            ):
                stop_reason = "reached duration limit"
                break

            total_runs = next_iteration
            remaining_seconds = (
                max(int(deadline - time.monotonic()), 0)
                if plan.mode == "duration" and deadline is not None
                else None
            )
            emit_event(
                "iteration_started",
                {
                    "plan": plan,
                    "iteration": total_runs,
                    "remaining_seconds": remaining_seconds,
                    "delegated_loops": requested_loops if delegate_loops else None,
                },
            )

            if prepare_env is not None:
                prepare_env()

            last_exit_code = run_pytest()
            if delegate_loops:
                completed_raw = os.environ.get(STABILITY_COMPLETED_LOOPS_ENV, "")
                try:
                    loop_completed = max(loop_completed, int(completed_raw))
                except (TypeError, ValueError):
                    pass

            if last_exit_code == 0:
                payload: Dict[str, Any] = {"iteration": total_runs}
                if delegate_loops:
                    payload["completed_loops"] = loop_completed
                    payload["requested_loops"] = requested_loops
                emit_event("iteration_succeeded", payload)
                passed_runs += 1
                if delegate_loops and requested_loops and progress_cb is not None:
                    percent = int(loop_completed / requested_loops * 100)
                    progress_cb(min(100, max(0, percent)))
                elif plan.mode == "loops" and plan.loops and progress_cb is not None:
                    percent = int(passed_runs / plan.loops * 100)
                    progress_cb(percent)
            else:
                payload = {"iteration": total_runs, "exit_code": last_exit_code}
                if delegate_loops:
                    payload["completed_loops"] = loop_completed
                    payload["requested_loops"] = requested_loops
                emit_event("iteration_failed", payload)
                stop_reason = f"stopped after failure (exit code {last_exit_code})"
                break

            if delegate_loops:
                if last_exit_code == 0 and requested_loops and loop_completed >= requested_loops:
                    stop_reason = "completed requested loops"
                elif last_exit_code == 0 and requested_loops == 0:
                    stop_reason = "completed requested loops"
                if stop_reason:
                    break

            if (
                plan.mode == "duration"
                and deadline is not None
                and time.monotonic() >= deadline
            ):
                stop_reason = "reached duration limit"
                break

        if not stop_reason:
            if plan.mode == "loops":
                stop_reason = "completed requested loops"
            elif plan.mode == "duration":
                stop_reason = "reached duration limit"
            else:
                stop_reason = "stopped by controller"

        if delegate_loops:
            target = requested_loops or loop_completed or 1
            total_runs = target
            if last_exit_code == 0 and loop_completed < target:
                loop_completed = target
            if last_exit_code == 0:
                passed_runs = target
            else:
                passed_runs = min(loop_completed, target)
                if not stop_reason:
                    stop_reason = f"stopped after failure (exit code {last_exit_code})"

        elapsed_seconds = time.monotonic() - overall_start
        emit_event(
            "summary",
            {
                "plan": plan,
                "total_runs": total_runs,
                "passed_runs": passed_runs,
                "stop_reason": stop_reason,
                "elapsed_seconds": elapsed_seconds,
                "completed_loops": loop_completed if delegate_loops else None,
            },
        )

        return {
            "exit_code": last_exit_code,
            "total_runs": total_runs,
            "passed_runs": passed_runs,
            "stop_reason": stop_reason,
            "elapsed_seconds": elapsed_seconds,
        }
    finally:
        completed_value = os.environ.get(STABILITY_COMPLETED_LOOPS_ENV)
        for key, previous in previous_env.items():
            if previous is _sentinel:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        if completed_value is not None:
            # Preserve completed loops for callers that inspect the environment after restoration.
            os.environ[STABILITY_COMPLETED_LOOPS_ENV] = completed_value
