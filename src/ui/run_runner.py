"""Thread wrapper that drives the multiprocessing pytest worker."""
from __future__ import annotations

import datetime
import logging
import multiprocessing
import queue
import shutil
import tempfile
import time
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal

from src.util.constants import Paths
from .theme import STYLE_BASE, TEXT_COLOR
from .run_worker import _pytest_worker


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


