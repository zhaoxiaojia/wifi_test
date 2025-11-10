#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: run.py
@time: 2025/7/22 22:02
@desc:
'''
import logging
import multiprocessing
import queue
import os
import shutil
import sip
from dataclasses import dataclass
from typing import Any
# ui/run.py

from PyQt5.QtWidgets import QVBoxLayout, QTextEdit, QLabel, QFrame, QHBoxLayout, QApplication
from qfluentwidgets import (
    CardWidget,
    StrongBodyLabel,
    PushButton,
    ProgressBar,
    InfoBar,
    InfoBarPosition,
    FluentIcon,

)
from PyQt5.QtCore import (
    QThread,
    pyqtSignal,
    QPropertyAnimation,
    QEasingCurve,
    QRect,
    QEvent,
    Qt,
    QTimer,
    QSize
)
from PyQt5.QtGui import QTextCursor
import datetime
import re
import random
import sys
import time
from pathlib import Path
import traceback
import threading
import pytest
import io
import json
import tempfile
from contextlib import suppress
from src.util.constants import Paths, get_src_base
from src.util.pytest_redact import install_redactor_for_current_process
from src.test.stability import (
    is_stability_case_path,
    load_stability_plan,
    prepare_stability_environment,
    run_stability_plan,
)
from .theme import (
    ACCENT_COLOR,
    CONTROL_HEIGHT,
    ICON_SIZE,
    ICON_TEXT_SPACING,
    LEFT_PAD,
    STYLE_BASE,
    TEXT_COLOR,
    FONT_FAMILY,
    apply_theme,
    format_log_html,
)



class LiveLogWriter:
    """
    Class auto-generated documentation.

    Responsibility
    ---------------
    Summarize what this class represents, its main collaborators,
    and how it participates in the app's flow (construction, signals, lifecycle).

    Attributes
    ----------
    (Add key attributes here)
        Short description of each important attribute.

    Notes
    -----
    Auto-generated documentation. Extend with examples and edge cases as needed.
    """

    def __init__(self, emit_func):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        self.emit_func = emit_func
        self._lock = threading.Lock()
        self._buffer = ""

    def write(self, msg):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        # 保证分行和进度信号捕获
        with self._lock:
            self._buffer += msg
            while '\n' in self._buffer:
                line, self._buffer = self._buffer.split('\n', 1)
                self.emit_func(line.rstrip('\r'))

    def flush(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        with self._lock:
            if self._buffer:
                self.emit_func(self._buffer.rstrip('\r'))
                self._buffer = ""

    def isatty(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        return False  # 必须加上这个

    def fileno(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        raise io.UnsupportedOperation("Not a real file")


class _RunLogSession:
    """Manage stdout redirection and persistent logging for a worker process."""

    def __init__(self, q: multiprocessing.Queue, log_file_path_str: str | None):
        self._queue = q
        self._log_file_path = self._resolve_log_path(log_file_path_str)
        self._log_handle: io.TextIOWrapper | None = self._open_handle()
        self._log_write_failed = False
        self._writer = LiveLogWriter(self._handle_line)
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
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


class CaseRunner(QThread):
    """Background runner that executes pytest in a worker process."""

    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    report_dir_signal = pyqtSignal(str)

    def __init__(self, case_path: str, parent=None):
        super().__init__(parent)
        self.case_path = case_path
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

    def run(self):
        """Spawn the worker process and relay events to the UI."""
        logging.info("CaseRunner: preparing to start process for %s", self.case_path)
        self._should_stop = False
        python_log_path = self._prepare_python_log_path()
        self._python_log_path = python_log_path
        self._python_log_copied = False
        self._proc = self._start_worker_process(python_log_path)
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
        if self._case_start_time is not None:
            duration_ms = int((time.time() - self._case_start_time) * 1000)
            self.log_signal.emit(f"[PYQT_CASETIME]{duration_ms}")
            self._case_start_time = None
        self._queue.close()
        self._queue.join_thread()
        queue_msg = (
            f"<b style='color:gray;'>The queue will be closed, but the process will remain alive：{self._proc.is_alive() if self._proc else False}</b>"
        )
        self.log_signal.emit(queue_msg)
        for message in self._try_copy_python_log():
            self.log_signal.emit(message)

    def stop(self):
        """Request the worker process to terminate."""
        self._should_stop = True
        if self._proc and self._proc.is_alive():
            self._proc.terminate()

    def _start_worker_process(self, python_log_path: str | None) -> multiprocessing.Process:
        """Create and start the subprocess that executes pytest."""
        proc = self._ctx.Process(
            target=_pytest_worker,
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
                yield ("log", "<b style='color:red;'>The operation has been terminated！</b>")
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
        if payload.startswith("[PYQT_CASE]"):
            if self._case_start_time is not None:
                duration_ms = int((time.time() - self._case_start_time) * 1000)
                messages.append(f"[PYQT_CASETIME]{duration_ms}")
            self._case_start_time = time.time()
        elif payload.startswith("[PYQT_PROGRESS]") and self._case_start_time is not None:
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
        target_dir = Path(self._report_dir) if self._report_dir else Path(Paths.BASE_DIR) / "report"
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self._python_log_copied = True
            return messages
        target = target_dir / "python.log"
        if target.exists():
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



def _pytest_worker(
    case_path: str,
    q: multiprocessing.Queue,
    log_file_path_str: str | None = None,
):
    """Run pytest in a background process and stream status updates."""
    ctx: _WorkerContext | None = None
    try:
        ctx = _init_worker_env(case_path, q, log_file_path_str)
        _stream_pytest_events(ctx)
    except Exception as exc:
        tb = traceback.format_exc()
        q.put(("log", f"<b style='{STYLE_BASE} color:red;'>Execution failed：{exc}</b>"))
        q.put(("log", f"<pre style='{STYLE_BASE} color:{TEXT_COLOR};'>{tb}</pre>"))
    finally:
        if ctx is not None:
            _finalize_run(ctx)


class RunPage(CardWidget):
    """
    Class auto-generated documentation.

    Responsibility
    ---------------
    Summarize what this class represents, its main collaborators,
    and how it participates in the app's flow (construction, signals, lifecycle).

    Attributes
    ----------
    (Add key attributes here)
        Short description of each important attribute.

    Notes
    -----
    Auto-generated documentation. Extend with examples and edge cases as needed.
    """

    def __init__(self, case_path, display_case_path=None, config=None, parent=None):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        super().__init__(parent)
        stack = getattr(parent, "stackedWidget", None)
        idx = stack.indexOf(self) if stack else None
        logging.info(
            "RunPage.__init__ start id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )
        self.setObjectName("runPage")
        apply_theme(self)
        self.case_path = case_path
        self.config = config
        self.main_window = parent  # 保存主窗口引用（用于InfoBar父窗口）

        self.display_case_path = self._calc_display_path(case_path, display_case_path)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        self.case_path_label = StrongBodyLabel(self.display_case_path)
        apply_theme(self.case_path_label)
        self.case_path_label.setStyleSheet(
            f"border-left: 4px solid {ACCENT_COLOR}; padding-left: 8px; font-family:{FONT_FAMILY};"
        )
        self.case_path_label.setFixedHeight(CONTROL_HEIGHT)
        self.case_path_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.case_path_label.setVisible(True)
        layout.addWidget(self.case_path_label)

        self.log_area = QTextEdit(self)
        self.log_area.setStyleSheet(
            f"""
            QTextEdit {{
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(0,103,192,0.35);
                border-radius: 6px;
                padding: 6px;
                selection-background-color: {ACCENT_COLOR};
                selection-color: white;
                font-family: {FONT_FAMILY};
            }}
            """
        )
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(400)
        apply_theme(self.log_area)
        self.log_area.document().setMaximumBlockCount(2000)
        layout.addWidget(self.log_area, stretch=5)
        # 当前用例信息展示
        self.case_info_label = QLabel("Current case : ", self)
        apply_theme(self.case_info_label)
        self.case_info_label.setStyleSheet(
            f"border-left: 4px solid {ACCENT_COLOR}; padding-left: 8px; font-family:{FONT_FAMILY};"
        )
        # ← 新增：统一高度 & 垂直居中，避免看起来更“瘦”
        self.case_info_label.setFixedHeight(CONTROL_HEIGHT)
        self.case_info_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.case_info_label.setStyleSheet(
            f"border-left: 4px solid {ACCENT_COLOR}; "
            f"padding-left: 8px; padding-top:0px; padding-bottom:0px; "
            f"font-family:{FONT_FAMILY};"
        )
        layout.addWidget(self.case_info_label)
        self.process = QFrame(self)
        self.process.setFixedHeight(CONTROL_HEIGHT)
        self.process.setStyleSheet(
            f"""
            QFrame {{
                background-color: rgba(255,255,255,0.06);
                border: 1px solid rgba(0,103,192,0.35);  /* ← 淡蓝描边 */
                border-radius: 4px;
                font-family: {FONT_FAMILY};
            }}
            """
        )
        layout.addWidget(self.process)
        # 填充条（作为背景动画层）
        self.process_fill = QFrame(self.process)
        self.process_fill.setGeometry(0, 0, 0, CONTROL_HEIGHT)
        self.process_fill.setStyleSheet(
            f"QFrame {{ background-color: {ACCENT_COLOR}; border-radius: 4px; }}"
        )
        # 百分比文字（居中覆盖）
        self.process_label = QLabel("Process: 0%", self.process)
        self.process_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.process_label.setAlignment(Qt.AlignLeft)
        self.process_label.setAlignment(Qt.AlignVCenter)

        apply_theme(self.process_label)
        self.process_label.setStyleSheet(
            f"font-family: {FONT_FAMILY};"
        )
        self.process_label.setGeometry(self.process.rect())
        self.remaining_time_label = QLabel("Remaining : 00:00:00", self.process)
        self.remaining_time_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.remaining_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        apply_theme(self.remaining_time_label)
        self.remaining_time_label.setStyleSheet(f"font-family: {FONT_FAMILY};")
        self.remaining_time_label.setGeometry(self.process.rect())
        self.remaining_time_label.hide()
        # —— Remaining 倒计时：每秒刷新 ——
        self._remaining_time_timer = QTimer(self)
        self._remaining_time_timer.setInterval(1000)  # 1s
        self._remaining_time_timer.timeout.connect(self._on_remaining_tick)
        self._remaining_seconds = 0
        # —— Overtime（倒计时到 0 后继续计时）——
        self._remaining_overtime = False
        self._overtime_seconds = 0
        self.process.installEventFilter(self)  # 让容器尺寸变化时同步 label/fill
        self._progress_animation = None
        self._current_percent = 0
        self.action_btn = PushButton(self)
        self.action_btn.setObjectName("actionBtn")
        self.action_btn.setStyleSheet(
            f"""
            #actionBtn {{
                background-color: {ACCENT_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                height: {CONTROL_HEIGHT}px;
                font-family: {FONT_FAMILY};
                padding: 0 20px;
            }}
            #actionBtn:hover {{
                background-color: #0b5ea8;  /* 深一点 */
            }}
            #actionBtn:pressed {{
                background-color: #084a85;  /* 更深 */
            }}
            #actionBtn:disabled {{
                background-color: rgba(0,103,192,0.35);
                color: rgba(255,255,255,0.6);
            }}
            """
        )
        if hasattr(self.action_btn, "setUseRippleEffect"):
            self.action_btn.setUseRippleEffect(True)
        if hasattr(self.action_btn, "setUseStateEffect"):
            self.action_btn.setUseStateEffect(True)
        self.action_btn.setFixedHeight(CONTROL_HEIGHT)
        layout.addWidget(self.action_btn)
        self.setLayout(layout)
        self.reset()
        self.finished_count = 0
        self.total_count = 0
        self.avg_case_duration = 0
        self._duration_sum = 0
        self._current_has_fixture = False
        stack = getattr(self.main_window, "stackedWidget", None)
        idx = stack.indexOf(self) if stack else None
        logging.info(
            "RunPage.__init__ end id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )

    def eventFilter(self, obj, event):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        # 用 getattr 防止属性未创建时报 AttributeError；用 QEvent.Resize 做比较
        if obj is getattr(self, "process", None) and event.type() == QEvent.Resize:
            rect = self.process.rect()
            self.process_label.setGeometry(rect)
            self.remaining_time_label.setGeometry(rect)
            total_w = max(rect.width(), 1)
            w = total_w if self._current_percent >= 99 else int(total_w * self._current_percent / 100)
            self.process_fill.setGeometry(0, 0, w, rect.height())
        return super().eventFilter(obj, event)

    def _fixture_upsert(self, name: str, params: str):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        """按顺序 upsert：存在则更新参数，不存在则追加到末尾"""
        for i, (n, _) in enumerate(self._fixture_chain):
            if n == name:
                self._fixture_chain[i] = (name, params)
                break
        else:
            self._fixture_chain.append((name, params))
        self._rebuild_case_info_label()

    def _rebuild_case_info_label(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        """用基线 + 链式 fixture 重建 Current case 文本"""
        parts = [self._case_name_base.strip()]
        for n, p in self._fixture_chain:
            parts.append(f"{n}={p}")
        # 用竖线分隔，直观显示执行先后顺序
        self.case_info_label.setText(" | ".join(parts))

    def _append_log(self, msg: str):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        if "libpng warning: iCCP: known incorrect sRGB profile" in msg:
            return
        if msg.strip() == "KeyboardInterrupt":
            return
        if msg.startswith("[PYQT_FIX]"):
            info = json.loads(msg[len("[PYQT_FIX]"):])
            name = str(info.get("fixture", "")).strip()
            params = str(info.get("params", "")).strip()
            if name and params:
                self._fixture_upsert(name, params)  # 累计或原位更新，不覆盖其它 fixture
            return
        if msg.startswith("[PYQT_CASE]"):
            fn = msg[len("[PYQT_CASE]"):].strip()
            if fn != self._case_fn:
                # 只有用例真的变化时才清空链
                self._case_fn = fn
                self._fixture_chain = []
            # 无论是否变化，都更新基线文本
            self._case_name_base = f"Current case : {fn}"
            self._rebuild_case_info_label()
            return
        if msg.startswith("[PYQT_CASEINFO]"):
            info = json.loads(msg[len("[PYQT_CASEINFO]"):])
            fixtures = info.get("fixtures") or []
            self._current_has_fixture = bool(fixtures)
            self._update_remaining_time_label()
            return
        if msg.startswith("[PYQT_CASETIME]"):
            try:
                duration_ms = int(msg[len("[PYQT_CASETIME]"):])
            except ValueError:
                return
            self.finished_count += 1
            self._duration_sum += duration_ms
            self.avg_case_duration = self._duration_sum / self.finished_count
            self._update_remaining_time_label()
            return
        if msg.startswith("[PYQT_PROGRESS]"):
            parts = msg[len("[PYQT_PROGRESS]"):].strip().split("/")
            if len(parts) == 2:
                with suppress(ValueError):
                    self.finished_count = int(parts[0])
                    self.total_count = int(parts[1])
            self._update_remaining_time_label()
            return
        html = format_log_html(msg)
        self.log_area.append(html)
        doc = self.log_area.document()
        if doc.blockCount() > 5000:
            cursor = QTextCursor(doc.firstBlock())
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _format_hms(self, seconds: int) -> str:
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        s = max(0, int(seconds))
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"Remaining : {h:02d}:{m:02d}:{sec:02d}"

    def _start_remaining_timer(self, seconds: int):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        seconds = max(0, int(seconds))
        if seconds <= 0:
            # 不在这里停表；由 _on_remaining_tick() 或 _update_remaining_time_label() 决定
            return

        # 收到新的有效 ETA ⇒ 回到倒计时模式
        self._remaining_overtime = False
        # 只在差异较大时重置，避免 UI 跳动；若当前是 Overtime，则无条件重置
        if self._remaining_time_timer.isActive() and not self._remaining_overtime:
            if abs(seconds - self._remaining_seconds) < 3:
                return

        self._remaining_seconds = seconds
        self.remaining_time_label.setText(self._format_hms(self._remaining_seconds))
        self.remaining_time_label.show()
        if not self._remaining_time_timer.isActive():
            self._remaining_time_timer.start()

    def _stop_remaining_timer(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        if hasattr(self, "_remaining_time_timer"):
            self._remaining_time_timer.stop()
        self._remaining_overtime = False
        self._overtime_seconds = 0
        if hasattr(self, "remaining_time_label"):
            self.remaining_time_label.hide()

    def _on_remaining_tick(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        if self._remaining_overtime:
            # Overtime：每秒 +1
            self._overtime_seconds += 1
            self.remaining_time_label.setText(f"Overtime : {self._format_hms(self._overtime_seconds)[12:]}")
            return

        # 倒计时模式：每秒 -1
        self._remaining_seconds -= 1
        if self._remaining_seconds <= 0:
            # 还有任务？→ 切 Overtime；没有任务 → 停表隐藏
            remaining_cases = max(self.total_count - self.finished_count, 0)
            runner_running = bool(getattr(self, "runner", None) and self.runner.isRunning())
            if remaining_cases > 0 or runner_running:
                self._remaining_overtime = True
                self._overtime_seconds = 0
                self.remaining_time_label.setText("Overtime : 00:00:00")
                self.remaining_time_label.show()
                # 计时器继续跑，由本函数负责递增
                return
            else:
                self._stop_remaining_timer()
                return

        # 正常倒计时刷新
        self.remaining_time_label.setText(self._format_hms(self._remaining_seconds))

    def _update_remaining_time_label(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        if not hasattr(self, "remaining_time_label"):
            return

        remaining_cases = max(self.total_count - self.finished_count, 0)

        # 全部完成：停表隐藏
        if remaining_cases <= 0:
            self._stop_remaining_timer()
            return

        # 有新 ETA ⇒ 重置倒计时（会自动退出 Overtime）
        remaining_ms = self.avg_case_duration * remaining_cases
        seconds = int(remaining_ms // 1000) if remaining_ms > 0 else -1
        if seconds > 0:
            self._start_remaining_timer(seconds)
            return

        # 无新 ETA：
        # 1) 若已在 Overtime，保持不动（继续每秒递增）；
        # 2) 若不在 Overtime 且计时器未启动，保持静默（避免闪烁）。
        if not self._remaining_time_timer.isActive() and not self._remaining_overtime:
            # 你也可在此显示“Estimating...”占位
            # self.remaining_time_label.setText("Remaining : estimating...")
            # self.remaining_time_label.show()
            pass

    def update_progress(self, percent: int):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        # 1) 归一化 & 记录
        percent = max(0, min(100, int(percent)))
        self._current_percent = percent

        # 2) 文本
        self.process_label.setText(f"Process: {percent}%")

        # 3) 颜色（使用你的主题蓝）
        try:
            color = ACCENT_COLOR  # 若未定义 ACCENT_COLOR，则改成 "#0067c0"
        except NameError:
            color = "#0067c0"
        self.process_fill.setStyleSheet(
            f"QFrame {{ background-color: {color}; border-radius: 4px; }}"
        )

        # 4) 目标宽度（100% 直接吃满，避免取整误差）
        rect = self.process.rect()
        total_w = rect.width() or 300
        target_w = total_w if percent >= 99 else int(total_w * percent / 100)

        # 5) 小于 2 像素的变化直接定位，避免末段频繁动画卡顿
        current_geo = self.process_fill.geometry()
        current_w = current_geo.width()

        if abs(target_w - current_w) < 2:
            self.process_fill.setGeometry(0, 0, target_w, rect.height())
            return

        # 6) 正常做平滑动画
        anim = QPropertyAnimation(self.process_fill, b"geometry")
        anim.setDuration(300)
        anim.setStartValue(current_geo)
        anim.setEndValue(QRect(0, 0, target_w, rect.height()))
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._progress_animation = anim

    def _trigger_config_run(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        """触发配置页的运行逻辑，确保与配置页按钮一致"""
        cfg_page = getattr(self.main_window, "case_config_page", None)
        if cfg_page and not sip.isdeleted(cfg_page):
            cfg_page.on_run()
        else:
            # 回退到直接运行当前 case
            self.run_case()

    def _set_action_button(self, mode: str):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        with suppress(TypeError):
            self.action_btn.clicked.disconnect()
        if mode == "run":
            text, slot = "Run", self._trigger_config_run
        elif mode == "stop":
            text, slot = "Stop", self.on_stop
        else:
            raise ValueError(f"Unknown mode: {mode}")
        self.action_btn.setText(text)
        self.action_btn.clicked.connect(lambda: logging.info("action_btn clicked"))
        self.action_btn.clicked.connect(slot)
        logging.info("Action button set to %s mode for RunPage id=%s", mode, id(self))

    def reset(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        with suppress(Exception):
            self.cleanup()
        self.log_area.clear()
        self.update_progress(0)
        self.remaining_time_label.hide()
        self._stop_remaining_timer()
        self._case_fn = ""
        self._case_name_base = "Current case : "
        self._fixture_chain = []
        self.case_info_label.setText(self._case_name_base)
        self._set_action_button("run")
        self.action_btn.setEnabled(True)

    def run_case(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        self.reset()
        self._set_action_button("stop")
        self.runner = CaseRunner(self.case_path)
        self.runner.log_signal.connect(self._append_log)
        self.runner.progress_signal.connect(self.update_progress)
        # notify main window when report directory is ready
        with suppress(Exception):
            self.runner.report_dir_signal.connect(self._on_report_dir_ready)
        # 关键修改：InfoBar的父窗口改为主窗口（而非RunPage自身）
        # self.runner.finished.connect(
        #     lambda: InfoBar.success(
        #         title="Done",
        #         content="Test Done",
        #         parent=self.main_window,  # 这里改为主窗口
        #         position=InfoBarPosition.TOP,
        #         duration=1800,
        #     )
        # )
        self.runner.finished.connect(self._finalize_runner)
        self.runner.start()

    def _finalize_runner(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        runner = getattr(self, "runner", None)
        if not runner:
            self.on_runner_finished()
            return
        for signal, slot in (
                (runner.log_signal, self._append_log),
                (runner.progress_signal, self.update_progress),
        ):
            with suppress((TypeError, RuntimeError)):
                signal.disconnect(slot)
        with suppress((TypeError, RuntimeError)):
            runner.report_dir_signal.disconnect(self._on_report_dir_ready)
        with suppress((TypeError, RuntimeError)):
            runner.finished.disconnect(self._finalize_runner)
        runner.deleteLater()
        self.runner = None
        self.on_runner_finished()

    def _on_report_dir_ready(self, path: str) -> None:
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        """Enable report page when report dir is created."""
        try:
            mw = getattr(self, "main_window", None) or self.window()
            if mw and hasattr(mw, "enable_report_page"):
                mw.enable_report_page(path)
        except Exception:
            pass

    def cleanup(self, disconnect_page: bool = True):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        stack = getattr(self.main_window, "stackedWidget", None)
        idx = stack.indexOf(self) if stack else None
        logging.info(
            "RunPage.cleanup start id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )
        self.remaining_time_label.hide()
        runner = getattr(self, "runner", None)
        if not runner:
            return
        logging.info("runner isRunning before wait: %s", runner.isRunning())
        runner.stop()
        logging.getLogger().handlers[:] = runner.old_handlers
        logging.getLogger().setLevel(runner.old_level)
        logging.info(
            "before terminate: isRunning=%s threadId=%s",
            runner.isRunning(),
            int(runner.currentThreadId()),
        )
        elapsed = 0
        step = 500
        timeout = 5000
        while not runner.wait(step):
            QApplication.processEvents()
            elapsed += step
            if elapsed >= timeout:
                logging.warning(
                    "runner thread did not finish within %s ms", timeout
                )
                # InfoBar.warning(
                #     title="Warning",
                #     content="线程未能及时结束",
                #     parent=self.main_window,
                #     position=InfoBarPosition.TOP,
                #     duration=3000,
                # )
                break
            logging.info(
                "runner.isRunning after wait: %s", runner.isRunning()
            )
        for signal, slot in (
                (runner.log_signal, self._append_log),
                (runner.progress_signal, self.update_progress),
        ):
            with suppress((TypeError, RuntimeError)):
                signal.disconnect(slot)
        with suppress((TypeError, RuntimeError)):
            runner.finished.disconnect(self.on_runner_finished)
        self.runner = None
        if disconnect_page:
            with suppress(TypeError):
                logging.info("Disconnecting signals for RunPage id=%s", id(self))
                self.disconnect()
                logging.info("Signals disconnected for RunPage id=%s", id(self))
        stack = getattr(self.main_window, "stackedWidget", None)
        idx = stack.indexOf(self) if stack else None
        logging.info(
            "RunPage.cleanup end id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )

    def on_runner_finished(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        self.cleanup()
        self._stop_remaining_timer()
        self._set_action_button("run")
        self.action_btn.setEnabled(True)
        self._case_fn = ""
        self._case_name_base = "Current case : "
        self._fixture_chain = []
        self.case_info_label.setText(self._case_name_base)

    def on_stop(self):
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        self._append_log("on_stop entered")
        self.cleanup()
        self._stop_remaining_timer()
        self._set_action_button("run")
        self.action_btn.setEnabled(True)

    def _get_application_base(self) -> Path:
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        return Path(get_src_base()).resolve()

    def _calc_display_path(self, case_path: str, display_case_path: str | None) -> str:
        """
        Summary
        -------
        Briefly describe what this function does. Expand with context:
        when it is called, what side effects it has, and its role in the flow.

        Parameters
        ----------
        (Add parameters here)
            Description of each parameter.

        Returns
        -------
        Any
            Description of the return value.

        Raises
        ------
        Exception
            Describe possible error conditions if relevant.

        Notes
        -----
        This docstring was auto-generated; refine as needed to match real behavior.
        """
        if display_case_path:
            p = Path(display_case_path)
            if ".." not in p.parts and not p.drive and not p.is_absolute():
                return display_case_path.replace("\\", "/")
        app_base = self._get_application_base()
        display_case_path = Path(case_path).resolve()
        with suppress(ValueError):
            display_case_path = display_case_path.relative_to(app_base)
        return display_case_path.as_posix()
