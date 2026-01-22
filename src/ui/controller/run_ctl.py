from __future__ import annotations

from typing import Any
import io, contextlib
import logging
import multiprocessing, subprocess
import queue
import shutil
import tempfile
import time, json
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal, Qt

from src.util.constants import Paths
from src.ui.view.theme import STYLE_BASE, TEXT_COLOR
from src.test.stability import (
    is_stability_case_path,
    load_stability_plan,
    prepare_stability_environment,
    run_stability_plan,
)
from src.util.pytest_redact import install_redactor_for_current_process
import pytest, os, sys
import pandas as pd

try:
    from src.test.conftest import _generate_allure_report_cli
except ImportError:
    _generate_allure_report_cli = None

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
    finished_signal = pyqtSignal()

    def __init__(self, case_path: str, account_name: str | None = None, display_case_path: str | None = None, shared_allure_results_dir: str | Path | None = None,
                 shared_pytest_log_file: str | Path | None = None, parent=None):
        super().__init__(parent)
        self.case_path = case_path
        self.account_name = (account_name or "").strip()
        self.display_case_path = display_case_path or case_path
        self.last_exit_code: int = 0
        # 存储共享路径（可能为 None）
        self._shared_allure_results_dir = Path(shared_allure_results_dir) if shared_allure_results_dir else None
        self._shared_pytest_log_file = Path(shared_pytest_log_file) if shared_pytest_log_file else None

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
            elif kind == "exit_code":
                self.last_exit_code = int(payload)
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
        self.finished_signal.emit()

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
            args=(
                self.case_path,
                self._queue,
                python_log_path,
                # 传递共享路径
                str(self._shared_allure_results_dir) if self._shared_allure_results_dir else None,
                str(self._shared_pytest_log_file) if self._shared_pytest_log_file else None,
            ),
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
            return messages
        src = Path(self._python_log_path)
        if not src.exists():
            self._python_log_copied = True
            return messages

        # 优先使用共享日志文件路径
        if self._shared_pytest_log_file:
            target = self._shared_pytest_log_file
        else:
            # 原有逻辑：使用自己的报告目录
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
            # --- 【关键修改】改为追加模式，而不是复制 ---
            with open(src, 'r', encoding='utf-8') as f_src:
                content = f_src.read()
            with open(target, 'a', encoding='utf-8') as f_target:
                f_target.write("\n" + "=" * 50 + "\n")
                f_target.write(f"Logs from case runner (PID: {os.getpid()})\n")
                f_target.write("=" * 50 + "\n")
                f_target.write(content)
            # --- 【关键修改】结束 ---
        except Exception as exc:
            messages.append(
                f"<b style='{STYLE_BASE} color:red;'>Failed to append case log to {target}: {exc}</b>"
            )
            self._python_log_copied = True
            return messages

        self._python_log_copied = True
        messages.append(
            f"<span style='{STYLE_BASE} color:{TEXT_COLOR};'>Case log appended to {target}</span>"
        )
        return messages

def _is_project_test_script(case_path: str) -> bool:
    parts = Path(case_path).resolve().parts
    for i in range(len(parts) - 2):
        if (str(parts[i]).lower() == "src" and
            str(parts[i+1]).lower() == "test" and
            str(parts[i+2]).lower() == "project"):
            return True
    return False


def _extract_project_relative_path(case_path: str) -> Path:
    p = Path(case_path).resolve()
    parts = p.parts

    # 查找连续�?src/test/project
    for i in range(len(parts) - 2):
        if (str(parts[i]).lower() == "src" and
                str(parts[i + 1]).lower() == "test" and
                str(parts[i + 2]).lower() == "project"):
            # 返回 project/ 之后的所有部�?
            relative_parts = parts[i + 3:]  # 注意�?i+3，跳�?src/test/project
            return Path(*relative_parts)

    # 理论上不会执行到这里（因为调用前已判断）
    raise ValueError(f"Path does not contain 'src/test/project': {case_path}")

def _init_worker_env(
    case_path: str,
    q: multiprocessing.Queue,
    log_file_path_str: str | None = None,
    shared_allure_results_dir: str | None = None,  # 新增参数
    shared_pytest_log_file: str | None = None,     # 新增参数
) -> "_WorkerContext":
    """Prepare logging, report directories, and pytest arguments."""
    session = _RunLogSession(q, log_file_path_str)
    import os, sys,  random, subprocess, tempfile
    from datetime import datetime
    from pathlib import Path

    # --- 【关键】判断是否为共享模式 (ExcelPlanRunner) ---
    in_shared_mode = bool(shared_allure_results_dir)
    # ---

    if in_shared_mode:
        # ========== ExcelPlanRunner 共享模式 ==========
        allure_results_dir = Path(shared_allure_results_dir).resolve()
        report_dir = allure_results_dir.parent  # 主报告目录
        # 日志路径：优先使用传入的共享日志文件，否则在主报告目录下创建
        effective_log_path = (
            shared_pytest_log_file
            or report_dir / "pytest.log"
        )
    else:
        # ========== 单 Case 独立模式（完全保留原始逻辑）==========
        timestamp = datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
        pid = os.getpid()
        timestamp = f"{timestamp}_{random.randint(1000, 9999)}"
        report_dir = (Path.cwd() / "report" / timestamp).resolve()
        report_dir.mkdir(parents=True, exist_ok=True)
        allure_results_dir = report_dir / "allure_report"
        effective_log_path = log_file_path_str or str(report_dir / "python.log")
    # ============================================

    # --- 【关键修改】将 effective_log_path 传给 _RunLogSession ---
    session = _RunLogSession(q, str(effective_log_path))

    # --- 通知队列报告目录 ---
    from contextlib import suppress
    with suppress(Exception):
        q.put(("report_dir", str(report_dir)))
    # ---

    plugin = install_redactor_for_current_process()

    # --- CORRECT PATH HANDLING (兼容开发/打包) ---
    input_path = Path(case_path)
    if input_path.is_absolute():
        absolute_test_path = input_path.resolve()
    else:
        if getattr(sys, 'frozen', False):  # 打包模式
            base_dir = Path(sys._MEIPASS)
        else:  # 开发模式
            base_dir = Path(__file__).resolve().parents[3]
        absolute_test_path = base_dir / "src/test/project" / case_path
        if not absolute_test_path.exists():
            raise FileNotFoundError(f"Test file not found: {absolute_test_path}")

    try:
        relative_path = absolute_test_path.relative_to(Path.cwd())
        pytest_case_path = str(relative_path).replace("\\", "/")
    except ValueError:
        pytest_case_path = str(absolute_test_path)
    os.environ["PYTEST_REPORT_DIR"] = str(report_dir)
    # --- END PATH HANDLING ---

    # --- 构建 pytest 参数 ---
    pytest_args = [
        "--rootdir=.",
        "--import-mode=importlib",
        f"--resultpath={report_dir}",
        #f"--alluredir={allure_results_dir}",
        "--alluredir", str(allure_results_dir),
        pytest_case_path,
    ]
    # ---

    # --- 添加 DUT 配置 ---
    from src.util.constants import load_config
    cfg = load_config(refresh=True)
    connect_cfg = cfg.get("connect_type") or {}
    dut_type = connect_cfg.get("type")
    match dut_type:
        case "Android":
            pytest_args.append("--dut-type=Android")
            android_cfg = connect_cfg.get("Android") or {}
            device = android_cfg.get("device")
            if device:
                pytest_args.append(f"--android-device={device}")
        case "Linux":
            pytest_args.append("--dut-type=Linux")
            telnet_cfg = connect_cfg.get("Linux") or {}
            ip = telnet_cfg.get("ip")
            if ip:
                pytest_args.append(f"--linux-ip={ip}")
    project_cfg = cfg.get("project") or {}
    customer = project_cfg.get("customer")
    if customer:
        pytest_args.append(f"--project-customer={customer}")
    # ---

    # --- 处理稳定性测试 ---
    is_stability_case = is_stability_case_path(case_path)
    plan = load_stability_plan() if is_stability_case else None
    pytest_args = _apply_exitfirst_flags(pytest_args, plan)
    # ---

    return _WorkerContext(
        case_path=pytest_case_path,
        queue=q,
        pytest_args=pytest_args,
        report_dir=report_dir,
        plugin=plugin,
        is_stability_case=is_stability_case,
        plan=plan if is_stability_case else None,
        log_session=session,
        # --- 传递日志路径给 _RunLogSession ---
        #effective_log_path=str(effective_log_path),
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
        #exit_code = pytest.main(ctx.pytest_args, plugins=[ctx.plugin])
        plugins_to_load = [ctx.plugin, 'allure_pytest']
        if getattr(sys, 'frozen', False):
            plugins_to_load = [ctx.plugin, 'allure_pytest.plugin']
        exit_code = pytest.main(ctx.pytest_args, plugins=plugins_to_load)
        print(f"[PYTEST ARGS] {ctx.pytest_args}")
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

    q.put(("exit_code", last_exit_code))
def _finalize_run(ctx: "_WorkerContext") -> None:
    """Restore stdout/loggers and emit the python log path event."""
    ctx.log_session.close()


def _pytest_worker(
    case_path: str,
    q: multiprocessing.Queue,
    log_file_path_str: str | None = None,
    shared_allure_results_dir: str | None = None,
    shared_pytest_log_file: str | None = None,
) -> None:
    """Spawned multiprocessing entrypoint that runs pytest and streams logs."""
    # ctx = _init_worker_env(
    #     case_path, q, log_file_path_str,
    #     shared_allure_results_dir,
    #     shared_pytest_log_file,
    # )
    ctx = None

    try:
        #ctx = _init_worker_env(case_path, q, log_file_path_str)
        ctx = _init_worker_env(
            case_path, q,
            log_file_path_str=log_file_path_str,  # 原始参数
            shared_allure_results_dir=shared_allure_results_dir,
            shared_pytest_log_file=shared_pytest_log_file,
        )
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


class ExcelPlanRunner(QThread):
    """
    Runner for executing a test plan from an Excel file.
    It reuses the existing CaseRunner for execution and updates the Excel with results.
    """
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    report_dir_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    case_report_ready_signal = pyqtSignal(str)

    def __init__(self, excel_path: str, parent=None):
        super().__init__(parent)
        self.excel_path = excel_path
        self._current_case_runner = None

        # --- 260105 新增：保存并接管根日志记录器的处理器 ---
        import logging
        root_logger = logging.getLogger()
        self.old_handlers = root_logger.handlers[:]
        self.old_level = root_logger.level

        # 清空处理器，防止日志污染主进程
        root_logger.handlers.clear()
        # --- End of new block ---

    def run(self):
        try:
            # --- 1. 创建主报告目录 ---
            timestamp = datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
            self._plan_report_dir = Path("report") / f"{timestamp}_{os.getpid()}"
            self._plan_report_dir.mkdir(parents=True, exist_ok=True)
            self.log_signal.emit(f"<b>计划报告目录已创建: {self._plan_report_dir}</b>")
            self.report_dir_signal.emit(str(self._plan_report_dir))
            print(f"[DEBUG ExcelPlanRunner] Emitted report dir: {self._plan_report_dir}")
            # --- 新增：复制主 Excel 计划到报告目录 ---
            self._local_excel_path = self._plan_report_dir / "test_result.xlsx"
            shutil.copy2(self.excel_path, self._local_excel_path)
            self.log_signal.emit(f"<b>测试计划已复制到: {self._local_excel_path}</b>")

            # --- 2. 创建共享资源 ---
            self._shared_allure_dir = self._plan_report_dir / "allure_report"
            self._shared_allure_dir.mkdir(parents=True, exist_ok=True)
            self._shared_pytest_log = self._plan_report_dir / "pytest.log"
            # ---
            self.report_dir_signal.emit(str(self._plan_report_dir))


            # 读取 Excel
            df = pd.read_excel(self.excel_path)
            if "Script Path" not in df.columns:
                raise ValueError("Excel file must contain a 'Script Path' column.")
            script_paths = df["Script Path"].dropna().tolist()
            total_cases = len(script_paths)
            if total_cases == 0:
                self.log_signal.emit("<b>No test cases to run.</b>")
                return

            self.log_signal.emit(f"<b>Starting plan with {total_cases} case(s)...</b>")

            for idx, script_path in enumerate(script_paths):
                if self.isInterruptionRequested():
                    self.log_signal.emit("<b style='color:red;'>Execution stopped by user.</b>")
                    break

                self.log_signal.emit(f"<br><b>▶️ Still Running: {script_path} ({idx + 1}/{total_cases})</b>")

                # --- 【核心】创建 CaseRunner 并传入共享路径 ---
                runner = CaseRunner(
                    case_path=str(script_path),
                    shared_allure_results_dir=self._shared_allure_dir,
                    shared_pytest_log_file=self._shared_pytest_log,
                )
                # ---

                # === 新增：监听子用例完成，更新实时报告 ===
                # def make_handler(index=idx, runner_ref=runner):
                #     def handler():
                #         # 更新 Excel 状态（原有逻辑）
                #         exit_code = runner_ref.last_exit_code
                #         status = "Passed" if exit_code == 0 else "Failed"
                #         print(f"[ExcelPlanRunner DEBUG] Case {index}: exit_code={exit_code}, status={status}")
                #         self._update_excel_result(index, status)
                #         # 👇 新增：生成实时 Allure 报告
                #         self._safe_generate_allure_report()
                #
                #     return handler

                #runner.finished_signal.connect(make_handler())

                # 连接信号
                runner.report_dir_signal.connect(self.case_report_ready_signal, Qt.DirectConnection)
                runner.log_signal.connect(self.log_signal)
                #runner.log_signal.connect(self.log_signal, Qt.QueuedConnection)
                #runner.report_dir_signal.connect(self.report_dir_signal)
                self._current_case_runner = runner

                runner.start()
                runner.wait()

                self._current_case_runner = None

                # 更新 Excel 状态
                exit_code = runner.last_exit_code
                status = "Passed" if runner.last_exit_code == 0 else "Failed"
                print(f"[RELIABLE DEBUG] Row {idx}: exit_code={exit_code}, status={status}")
                self._update_excel_result(idx, status)

                # 发射整体进度
                self.progress_signal.emit(int((idx + 1) / total_cases * 100))

            self.log_signal.emit(f"<b>✅ 所有用例执行完毕！完整报告位于: {self._plan_report_dir}</b>")
            self.finished_signal.emit()

        except Exception as e:
            error_msg = f"<b style='color:red;'>Plan runner error: {e}</b>"
            self.log_signal.emit(error_msg)
            import traceback
            self.log_signal.emit(f"<b style='color:red;'>Error in ExcelPlanRunner: {e}</b>")
            self.log_signal.emit(f"<pre>{traceback.format_exc()}</pre>")
            self.finished_signal.emit()
        finally:
            # 恢复根日志记录器（您原有的代码）
            import logging
            root_logger = logging.getLogger()
            root_logger.handlers.clear()
            for handler in getattr(self, 'old_handlers', []):
                root_logger.addHandler(handler)
            root_logger.setLevel(getattr(self, 'old_level', logging.WARNING))
            self.finished_signal.emit()

    def _update_excel_result(self, row_index: int, status: str):
        """Update the 'Status' column in the Excel file."""
        try:
            exit_code = self._current_case_runner.last_exit_code if self._current_case_runner else "N/A"
            print(f"[DEBUG] Row {row_index}: exit_code={exit_code}, status={status}")

            df = pd.read_excel(self.excel_path)
            df.loc[row_index, "Status"] = status
            df.to_excel(self.excel_path, index=False, engine='openpyxl')
        except Exception as e:
            self.log_signal.emit(f"<b style='color:orange;'>Failed to update Excel: {e}</b>")

    # --- 在 ExcelPlanRunner 类中新增方法 ---
    def _merge_directories(self, src: Path, dst: Path):
        """
        Recursively merge the contents of src directory into dst directory.
        If a file exists in both, the one from src will overwrite the one in dst.
        """
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            dest_item = dst / item.name
            if item.is_dir():
                self._merge_directories(item, dest_item)
            else:
                shutil.copy2(item, dest_item)

    def _safe_generate_allure_report(self) -> bool:
        """
        Safely generate Allure HTML report from shared allure_report directory.
        Only used in ExcelPlanRunner for real-time preview.
        Does NOT affect CaseRunner's own report generation.
        """
        if _generate_allure_report_cli is None:
            print("[WARN] conftest._generate_allure_report_cli not available")
            return False

        if not hasattr(self, '_plan_report_dir'):
            return False

        input_dir = self._plan_report_dir / "allure_report"
        output_dir = self._plan_report_dir / "allure_results"  # 连字符，区别于单例模式

        # 必须存在 .json 文件才生成
        if not input_dir.exists() or not any(input_dir.glob("*.json")):
            return False

        try:
            # 调用原始函数（与最终报告生成逻辑完全一致）
            _generate_allure_report_cli(input_dir, output_dir)
            print(f"[ExcelPlanRunner] Real-time Allure report updated: {output_dir}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to generate real-time Allure report: {e}")
            return False

    def stop(self) -> None:
        """Stop the runner and its current child CaseRunner if any."""
        self.requestInterruption()

        # 260105 如果有正在运行的子 CaseRunner，也尝试停止它
        if self._current_case_runner is not None:
            try:
                self._current_case_runner.stop()
            except Exception as e:
                logging.warning("Failed to stop child CaseRunner: %s", e)

__all__ = ["reset_wizard_after_run", "LiveLogWriter", "CaseRunner", "ExcelPlanRunner"]

