"""Background worker orchestration for the run page."""
from __future__ import annotations

import datetime
import logging
import multiprocessing
import random
import traceback
from contextlib import suppress
from pathlib import Path
from typing import Any
from dataclasses import dataclass
import pytest

from src.test.stability import (
    is_stability_case_path,
    load_stability_plan,
    prepare_stability_environment,
    run_stability_plan,
)
from src.util.constants import Paths
from src.util.pytest_redact import install_redactor_for_current_process
from .theme import STYLE_BASE, TEXT_COLOR
from .run_log import _RunLogSession

__all__ = ["_pytest_worker"]


@dataclass
class _WorkerContext:
    """Describe a pytest worker execution context."""

    case_path: str
    queue: multiprocessing.Queue
    pytest_args: list[str]
    report_dir: Path
    plugin: Any
    is_stability_case: bool
    plan: Any | None
    log_session: _RunLogSession


def _init_worker_env(
    case_path: str, q: multiprocessing.Queue, log_file_path_str: str | None
) -> _WorkerContext:
    """Prepare logging, report directories, and pytest arguments."""
    session = _RunLogSession(q, log_file_path_str)
    timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
    timestamp = f"{timestamp}_{random.randint(1000, 9999)}"
    report_dir = (Path.cwd() / "report" / timestamp).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    with suppress(Exception):
        q.put(("report_dir", str(report_dir)))
    plugin = install_redactor_for_current_process()
    pytest_args = [
        "-v",
        "-s",
        "--full-trace",
        "--rootdir=.",
        "--import-mode=importlib",
        f"--resultpath={report_dir}",
        case_path,
    ]
    is_stability_case = is_stability_case_path(case_path)
    plan = load_stability_plan() if is_stability_case else None
    return _WorkerContext(
        case_path=case_path,
        queue=q,
        pytest_args=pytest_args,
        report_dir=report_dir,
        plugin=plugin,
        is_stability_case=is_stability_case,
        plan=plan,
        log_session=session,
    )


def _stream_pytest_events(ctx: _WorkerContext) -> None:
    """Execute pytest (or the stability harness) and forward updates via queue."""
    q = ctx.queue
    q.put(("log", f"<b style='{STYLE_BASE} color:#a6e3ff;'>Run pytest</b>"))
    last_exit_code = 0

    def emit_stability_event(kind: str, payload: dict[str, Any]) -> None:
        if kind == "plan_started":
            plan_info = payload["plan"]
            target_desc = (
                f"{plan_info.loops} loops"
                if plan_info.mode == "loops"
                else f"{plan_info.duration_hours} hours"
                if plan_info.mode == "duration"
                else "until stopped"
            )
            q.put(
                (
                    "log",
                    f"<span style='{STYLE_BASE} color:{TEXT_COLOR};'>[Stability] Mode: {plan_info.mode}, target: {target_desc}.</span>",
                )
            )
        elif kind == "iteration_started":
            plan_info = payload["plan"]
            iteration = payload["iteration"]
            if plan_info.mode == "loops":
                phase_desc = f"loop {iteration}/{plan_info.loops}"
            elif plan_info.mode == "duration":
                remaining = payload.get("remaining_seconds") or 0
                remaining_hours = max(remaining / 3600, 0.0)
                duration_hours = plan_info.duration_hours or 0
                phase_desc = f"target {duration_hours} h ({remaining_hours:.2f}h left)"
            else:
                phase_desc = "running until stopped"
            q.put(
                (
                    "log",
                    f"<span style='{STYLE_BASE} color:{TEXT_COLOR};'>[Stability] Iteration {iteration} started ({phase_desc}).</span>",
                )
            )
        elif kind == "iteration_succeeded":
            iteration = payload["iteration"]
            q.put(
                (
                    "log",
                    f"<span style='{STYLE_BASE} color:{TEXT_COLOR};'>[Stability] Iteration {iteration} finished successfully.</span>",
                )
            )
        elif kind == "iteration_failed":
            iteration = payload["iteration"]
            exit_code = payload["exit_code"]
            q.put(
                (
                    "log",
                    f"<b style='{STYLE_BASE} color:red;'>[Stability] Iteration {iteration} failed with exit code {exit_code}; aborting remaining runs.</b>",
                )
            )
        elif kind == "summary":
            total_runs = payload["total_runs"]
            passed_runs = payload["passed_runs"]
            stop_reason = payload["stop_reason"]
            elapsed_seconds = payload["elapsed_seconds"]
            summary_color = "#a6e3ff" if passed_runs == total_runs else "red"
            summary = (
                f"[Stability] Summary: {passed_runs}/{total_runs} runs finished, {stop_reason}. "
                f"Elapsed {elapsed_seconds / 60:.1f} min."
            )
            q.put(
                (
                    "log",
                    f"<b style='{STYLE_BASE} color:{summary_color};'>{summary}</b>",
                )
            )

    def emit_stability_progress(percent: int) -> None:
        q.put(("progress", percent))

    if ctx.is_stability_case and ctx.plan is not None:
        result = run_stability_plan(
            ctx.plan,
            run_pytest=lambda: pytest.main(ctx.pytest_args, plugins=[ctx.plugin]),
            prepare_env=prepare_stability_environment,
            emit_event=emit_stability_event,
            progress_cb=emit_stability_progress,
        )
        last_exit_code = result["exit_code"]
    else:
        exit_code = pytest.main(ctx.pytest_args, plugins=[ctx.plugin])
        last_exit_code = exit_code
        if exit_code != 0:
            failure_msg = (
                f"<b style='{STYLE_BASE} color:red;'>Pytest failed with exit code {exit_code}.</b>"
            )
            q.put(("log", failure_msg))
    if last_exit_code == 0:
        q.put(("log", f"<b style='{STYLE_BASE} color:#a6e3ff;'>Test completed ！</b>"))
    elif not ctx.is_stability_case:
        q.put(
            (
                "log",
                f"<b style='{STYLE_BASE} color:red;'>Pytest exited with code {last_exit_code}.</b>",
            )
        )


def _finalize_run(ctx: _WorkerContext) -> None:
    """Restore stdout/loggers and emit the python log path event."""
    ctx.log_session.close()


def _pytest_worker(
    case_path: str,
    q: multiprocessing.Queue,
    log_file_path_str: str | None = None,
) -> None:
    """Spawned multiprocessing entrypoint that runs pytest and streams logs."""
    ctx: _WorkerContext | None = None
    try:
        ctx = _init_worker_env(case_path, q, log_file_path_str)
        _stream_pytest_events(ctx)
    except Exception as exc:  # pragma: no cover - defensive logging in worker
        tb = traceback.format_exc()
        q.put(("log", f"<b style='{STYLE_BASE} color:red;'>Execution failed: {exc}</b>"))
        q.put(("log", f"<pre style='{STYLE_BASE} color:{TEXT_COLOR};'>{tb}</pre>"))
    finally:
        if ctx is not None:
            _finalize_run(ctx)


