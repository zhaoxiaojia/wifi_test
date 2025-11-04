"""Utilities shared by stability stress test suites."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional
import sys
import time

__all__ = [
    "StabilityPlan",
    "is_stability_case_path",
    "load_stability_plan",
    "prepare_stability_environment",
    "run_stability_plan",
    "STABILITY_COMPLETED_LOOPS_ENV",
    "STABILITY_LOOPS_ENV",
    "STABILITY_MODE_ENV",
    "STABILITY_DURATION_ENV",
]


STABILITY_MODE_ENV = "WIFI_STABILITY_MODE"
STABILITY_LOOPS_ENV = "WIFI_STABILITY_LOOPS"
STABILITY_DURATION_ENV = "WIFI_STABILITY_DURATION_MINUTES"
STABILITY_COMPLETED_LOOPS_ENV = "WIFI_STABILITY_COMPLETED_LOOPS"


@dataclass(frozen=True)
class StabilityPlan:
    """Normalized stability execution plan."""

    mode: str
    loops: int
    duration_minutes: int


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


def normalize_stability_config(raw_value: Any) -> StabilityPlan:
    """Normalize persisted stability plan for safe execution."""

    defaults = {"mode": "loops", "loops": 1, "duration_minutes": 5}
    if isinstance(raw_value, dict):
        normalized: Dict[str, Any] = dict(raw_value)
    else:
        normalized = {}

    mode_text = str(normalized.get("mode", defaults["mode"])).strip().lower()
    if mode_text not in {"loops", "duration"}:
        mode_text = "loops"

    def _coerce(key: str, fallback: int, limit: int) -> int:
        try:
            value = int(normalized.get(key, fallback))
        except (TypeError, ValueError):
            value = fallback
        if value <= 0:
            value = fallback
        return min(value, limit)

    loops = _coerce("loops", defaults["loops"], 999_999)
    duration = _coerce("duration_minutes", defaults["duration_minutes"], 24 * 60)
    return StabilityPlan(mode_text, loops, duration)


def load_stability_plan() -> StabilityPlan:
    """Load and normalize the current stability execution plan."""

    from src.tools.config_loader import load_config

    snapshot = load_config(refresh=True) or {}
    return normalize_stability_config(snapshot.get("stability_conditions"))


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
    requested_loops = plan.loops if plan.mode == "loops" else 0
    total_runs = 0
    passed_runs = 0
    last_exit_code = 0
    stop_reason = ""
    overall_start = time.monotonic()
    deadline = (
        overall_start + plan.duration_minutes * 60
        if plan.mode == "duration"
        else None
    )
    loop_completed = 0

    env_updates: Dict[str, str] = {
        STABILITY_MODE_ENV: plan.mode,
        STABILITY_DURATION_ENV: str(plan.duration_minutes),
        STABILITY_COMPLETED_LOOPS_ENV: "0",
    }
    if delegate_loops:
        env_updates[STABILITY_LOOPS_ENV] = str(plan.loops)

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
            if plan.mode == "loops" and not delegate_loops and total_runs >= plan.loops:
                stop_reason = "completed requested loops"
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
                elif (
                    plan.mode == "loops"
                    and plan.loops
                    and progress_cb is not None
                ):
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
            stop_reason = (
                "completed requested loops"
                if plan.mode == "loops"
                else "reached duration limit"
            )

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

