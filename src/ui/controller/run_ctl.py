from __future__ import annotations

from typing import Any
import io
import logging
import multiprocessing
import queue
import shutil
import tempfile
import time
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from src.util.constants import Paths
from src.ui.view.theme import STYLE_BASE, TEXT_COLOR
from src.test.stability import (
    is_stability_case_path,
    load_stability_plan,
    prepare_stability_environment,
    run_stability_plan,
)
from src.util.pytest_redact import install_redactor_for_current_process
import pytest


def reset_wizard_after_run(page: Any) -> None:
    """Reset Config wizard state after a successful run.

    This helper centralises the post-run behaviour so that both the Config
    page and any other entry points can reuse the same logic:
    - navigate back to the first (DUT) page
    - re-sync Run button enabled state
    - restore second-page (Execution) CSV selection and enabled state
    """
    # Navigate back to DUT page if the stack is available.
    stack = getattr(page, "stack", None)
    if stack is not None and hasattr(stack, "setCurrentIndex"):
        try:
            stack.setCurrentIndex(0)
        except Exception:
            pass

    # Delegate button/CSV reset to the ConfigController when present.
    config_ctl = getattr(page, "config_ctl", None)
    if config_ctl is not None:
        try:
            config_ctl.sync_run_buttons_enabled()
        except Exception:
            pass
        try:
            config_ctl.reset_second_page_inputs()
        except Exception:
            pass


class LiveLogWriter:
    """Thread-safe stream-like object that forwards complete lines to a callback."""

    def __init__(self, emit_func):
        self.emit_func = emit_func
        self._lock = getattr(__import__("threading"), "Lock")()
        self._buffer = ""

    def write(self, msg: str) -> None:
        with self._lock:
            self._buffer += msg
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                self.emit_func(line.rstrip("\r"))

    def flush(self) -> None:
        with self._lock:
            if self._buffer:
                self.emit_func(self._buffer.rstrip("\r"))
                self._buffer = ""

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        raise io.UnsupportedOperation("Not a real file")


class _RunLogSession:
    """Manage stdout redirection and persistent logging for a worker process."""

    def __init__(self, q: multiprocessing.Queue, log_file_path_str: str | None):
        self._queue = q
        self._log_file_path = self._resolve_log_path(log_file_path_str)
        self._log_handle: io.TextIOWrapper | None = self._open_handle()
        self._log_write_failed = False
        self._writer = LiveLogWriter(self._handle_line)
        self._old_stdout = __import__("sys").stdout
        self._old_stderr = __import__("sys").stderr
        sys = __import__("sys")
        sys.stdout = sys.stderr = self._writer
        self._root_logger = logging.getLogger()
        self._old_handlers = self._root_logger.handlers[:]
        self._old_level = self._root_logger.level
        for handler in self._old_handlers:
            self._root_logger.removeHandler(handler)
        self._stream_handler = logging.StreamHandler(self._writer)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(filename)s:%(funcName)s(line:%(lineno)d) |  %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        self._stream_handler.setFormatter(formatter)
        self._root_logger.addHandler(self._stream_handler)
        self._root_logger.setLevel(logging.INFO)

    def _resolve_log_path(self, explicit: str | None) -> Path | None:
        if explicit:
            path = Path(explicit)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                return None
            return path
        workspace = getattr(Paths, "WORKSPACE", None)
        if workspace:
            base_dir = Path(workspace)
            base_dir.mkdir(parents=True, exist_ok=True)
        else:
            base_dir = Path(tempfile.mkdtemp(prefix="pytest_log_"))
        return base_dir / "python.log"

    def _open_handle(self) -> io.TextIOWrapper | None:
        if not self._log_file_path:
            return None
        try:
            return open(self._log_file_path, "w", encoding="utf-8")
        except Exception:
            return None

    def _handle_line(self, line: str) -> None:
        self._queue.put(("log", line))
        import re
        from contextlib import suppress

        match = re.search(r"\[PYQT_PROGRESS\]\s+(\d+)/(\d+)", line)
        if match:
            finished = int(match.group(1))
            total = int(match.group(2))
            percent = int(finished / total * 100) if total else 0
            self._queue.put(("progress", percent))
        if self._log_handle and not self._log_write_failed:
            try:
                self._log_handle.write(line + "\n")
                self._log_handle.flush()
            except Exception:
                self._log_write_failed = True
                with suppress(Exception):
                    self._log_handle.close()
                self._log_handle = None

    def close(self) -> None:
        from contextlib import suppress
        import sys

        for handler in self._root_logger.handlers[:]:
            self._root_logger.removeHandler(handler)
        for handler in self._old_handlers:
            self._root_logger.addHandler(handler)
        self._root_logger.setLevel(self._old_level)
        sys.stdout = self._old_stdout
        sys.stderr = self._old_stderr
        with suppress(Exception):
            self._writer.flush()
        if self._log_handle:
            with suppress(Exception):
                self._log_handle.flush()
            with suppress(Exception):
                self._log_handle.close()
        if self._log_file_path:
            with suppress(Exception):
                self._queue.put(("python_log", str(self._log_file_path)))


class CaseRunner(QThread):
    """Background runner that executes pytest in a worker process."""

    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    report_dir_signal = pyqtSignal(str)

    def __init__(self, case_path: str, account_name: str | None = None, display_case_path: str | None = None, parent=None):
        super().__init__(parent)
        self.case_path = case_path
        self.account_name = (account_name or "").strip()
        self.display_case_path = display_case_path or case_path
        self._ctx = multiprocessing.get_context("spawn")
        self._queue = self._ctx.Queue()
        self._proc: multiprocessing.Process | None = None
        self._report_dir: str | None = None
        self._python_log_path: str | None = None
        self._python_log_copied = False
        self._should_stop = False
        self._case_start_time: float | None = None
        root_logger = logging.getLogger()
        self.old_handlers = root_logger.handlers[:]
        self.old_level = root_logger.level

    def run(self) -> None:  # type: ignore[override]
        """Spawn the worker process and relay events to the UI."""
        from datetime import datetime

        run_started_at = datetime.now()
        run_started_ts = time.time()
        logging.info("CaseRunner: preparing to start process for %s", self.case_path)
        self._should_stop = False
        python_log_path = self._prepare_python_log_path()
        self._python_log_path = python_log_path
        self._python_log_copied = False
        from src.ui.controller.run_ctl import _pytest_worker  # local import

        self._proc = self._start_worker_process(python_log_path, _pytest_worker)
        logging.info(
            "CaseRunner: process started pid=%s for %s",
            self._proc.pid if self._proc else None,
            self.case_path,
        )
        for kind, payload in self._monitor_worker_events():
            if kind == "log":
                for message in self._normalize_log_messages(str(payload)):
                    self.log_signal.emit(message)
            elif kind == "progress":
                self.progress_signal.emit(payload)
            elif kind == "report_dir":
                self._report_dir = str(payload)
                self.report_dir_signal.emit(str(payload))
            elif kind == "python_log":
                self._python_log_path = str(payload)
        # Flush any in-flight case timing marker.
        if self._case_start_time is not None:
            duration_ms = int((time.time() - self._case_start_time) * 1000)
            self.log_signal.emit(f"[PYQT_CASETIME]{duration_ms}")
            self._case_start_time = None
        # Record aggregated pytest run duration for history.
        try:
            from src.util.test_history import append_test_history_record

            duration_seconds = max(0.0, time.time() - run_started_ts)
            test_case_label = getattr(self, "display_case_path", "") or self.case_path
            append_test_history_record(
                account_name=getattr(self, "account_name", "") or "",
                start_time=run_started_at,
                test_case=str(test_case_label),
                duration_seconds=duration_seconds,
            )
        except Exception as exc:
            logging.warning("CaseRunner: failed to record test history: %s", exc)
        self._queue.close()
        self._queue.join_thread()
        queue_msg = (
            f"<b style='color:gray;'>The queue will be closed, but the process will remain alive：{self._proc.is_alive() if self._proc else False}</b>"
        )
        self.log_signal.emit(queue_msg)
        for message in self._try_copy_python_log():
            self.log_signal.emit(message)

    def stop(self) -> None:
        """Request the worker process to terminate."""
        self._should_stop = True
        if self._proc and self._proc.is_alive():
            self._proc.terminate()

    def _start_worker_process(
        self,
        python_log_path: str | None,
        worker,
    ) -> multiprocessing.Process:
        """Create and start the subprocess that executes pytest."""
        proc = self._ctx.Process(
            target=worker,
            args=(self.case_path, self._queue, python_log_path),
        )
        proc.start()
        return proc

    def _monitor_worker_events(self):
        """Yield queue events and housekeeping log messages."""
        while True:
            if self._should_stop:
                if self._proc and self._proc.is_alive():
                    self._proc.terminate()
                    self._proc.join()
                yield ("log", "<b style='color:red;'>The operation has been terminated</b>")
                break
            event = self._next_worker_event()
            if event:
                yield event
                continue
            for message in self._try_copy_python_log():
                yield ("log", message)
            if self._proc and (not self._proc.is_alive()) and self._queue.empty():
                for message in self._try_copy_python_log():
                    yield ("log", message)
                queue_msg = (
                    f"<b style='color:gray;'>The queue will be closed, but the process will remain alive：{self._proc.is_alive()}</b>"
                )
                yield ("log", queue_msg)
                logging.info("closing queue; proc alive=%s", self._proc.is_alive())
                break

    def _next_worker_event(self):
        """Return the next payload tuple from the multiprocessing queue."""
        try:
            return self._queue.get(timeout=0.1)
        except queue.Empty:
            return None

    def _normalize_log_messages(self, payload: str) -> list[str]:
        """Inject synthetic CASETIME markers as needed for the UI."""
        messages: list[str] = []
        # Payload lines may include timestamps and prefixes; locate the raw marker.
        marker_index = payload.find("[PYQT_")
        marker = payload[marker_index:] if marker_index != -1 else payload

        if marker.startswith("[PYQT_CASE]"):
            if self._case_start_time is not None:
                duration_ms = int((time.time() - self._case_start_time) * 1000)
                messages.append(f"[PYQT_CASETIME]{duration_ms}")
            self._case_start_time = time.time()
        elif marker.startswith("[PYQT_PROGRESS]") and self._case_start_time is not None:
            duration_ms = int((time.time() - self._case_start_time) * 1000)
            messages.append(f"[PYQT_CASETIME]{duration_ms}")
            self._case_start_time = None
        messages.append(payload)
        return messages

    def _prepare_python_log_path(self) -> str | None:
        """Return a writable python.log path for the worker process."""
        try:
            base_dir = Path(Paths.BASE_DIR) / "report" / "python_logs"
            base_dir.mkdir(parents=True, exist_ok=True)
            temp_dir = Path(tempfile.mkdtemp(prefix="python_log_", dir=str(base_dir)))
            return str(temp_dir / "python.log")
        except Exception as exc:
            logging.warning("Failed to create python log path: %s", exc)
            return None

    def _try_copy_python_log(self) -> list[str]:
        """Copy python.log into the report directory once the process finishes."""
        messages: list[str] = []
        if self._python_log_copied or not self._python_log_path:
            return messages
        if self._proc and self._proc.is_alive():
            return messagesgit
        src = Path(self._python_log_path)
        if not src.exists():
            self._python_log_copied = True
            return messages
        target_dir = Path(self._report_dir) if self._report_dir else Path(Paths.BASE_DIR) / "report"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self._python_log_copied = True
            return messages
        target = target_dir / "python.log"
        if target.exists():
            import datetime

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            target = target_dir / f"python_{timestamp}.log"
        try:
            shutil.copy2(src, target)
        except Exception as exc:
            messages.append(
                f"<b style='{STYLE_BASE} color:red;'>Failed to copy python.log: {exc}</b>"
            )
            self._python_log_copied = True
            return messages
        self._python_log_copied = True
        messages.append(
            f"<span style='{STYLE_BASE} color:{TEXT_COLOR};'>Python log saved to {target}</span>"
        )
        return messages


def _init_worker_env(
    case_path: str, q: multiprocessing.Queue, log_file_path_str: str | None
) -> "_WorkerContext":
    """Prepare logging, report directories, and pytest arguments."""
    session = _RunLogSession(q, log_file_path_str)
    import random, datetime

    timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
    timestamp = f"{timestamp}_{random.randint(1000, 9999)}"
    report_dir = (Path.cwd() / "report" / timestamp).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    from contextlib import suppress

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

    # Only apply stability retry/exit-first flags for stability cases.
    is_stability_case = is_stability_case_path(case_path)
    plan = load_stability_plan() if is_stability_case else None
    pytest_args = _apply_exitfirst_flags(pytest_args, plan)

    return _WorkerContext(
        case_path=case_path,
        queue=q,
        pytest_args=pytest_args,
        report_dir=report_dir,
        plugin=plugin,
        is_stability_case=is_stability_case,
        plan=plan if is_stability_case else None,
        log_session=session,
    )


def _apply_exitfirst_flags(pytest_args: list[str], plan) -> list[str]:
    """Return pytest args extended with exit-first and retry flags when requested."""

    if plan is None or not getattr(plan, "exit_first", False) or not pytest_args:
        return pytest_args

    args = list(pytest_args)
    case_arg = args.pop() if args else None
    args.append("-x")
    retry_limit = max(0, int(getattr(plan, "retry_limit", 0) or 0))
    if retry_limit > 0:
        args.append(f"--count={retry_limit + 1}")
        args.append(f"--maxfail={retry_limit}")
    if case_arg is not None:
        args.append(case_arg)
    return args


def _stream_pytest_events(ctx: "_WorkerContext") -> None:
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
        q.put(("log", f"<b style='{STYLE_BASE} color:#a6e3ff;'>Test completed</b>"))
    elif not ctx.is_stability_case:
        q.put(
            (
                "log",
                f"<b style='{STYLE_BASE} color:red;'>Pytest exited with code {last_exit_code}.</b>",
            )
        )


def _finalize_run(ctx: "_WorkerContext") -> None:
    """Restore stdout/loggers and emit the python log path event."""
    ctx.log_session.close()


def _pytest_worker(
    case_path: str,
    q: multiprocessing.Queue,
    log_file_path_str: str | None = None,
    ctx: "_WorkerContext" | None = None
) -> None:
    """Spawned multiprocessing entrypoint that runs pytest and streams logs."""

    try:
        ctx = _init_worker_env(case_path, q, log_file_path_str)
        _stream_pytest_events(ctx)
    except Exception as exc:  # pragma: no cover - defensive logging in worker
        import traceback as _tb

        tb = _tb.format_exc()
        q.put(("log", f"<b style='{STYLE_BASE} color:red;'>Execution failed: {exc}</b>"))
        q.put(("log", f"<pre style='{STYLE_BASE} color:{TEXT_COLOR};'>{tb}</pre>"))
    finally:
        if ctx is not None:
            _finalize_run(ctx)


class _WorkerContext:
    """Describe a pytest worker execution context."""

    def __init__(
        self,
        case_path: str,
        queue: multiprocessing.Queue,
        pytest_args: list[str],
        report_dir: Path,
        plugin: Any,
        is_stability_case: bool,
        plan: Any | None,
        log_session: _RunLogSession,
    ) -> None:
        self.case_path = case_path
        self.queue = queue
        self.pytest_args = pytest_args
        self.report_dir = report_dir
        self.plugin = plugin
        self.is_stability_case = is_stability_case
        self.plan = plan
        self.log_session = log_session


__all__ = ["reset_wizard_after_run", "LiveLogWriter", "CaseRunner"]
