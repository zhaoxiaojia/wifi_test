"""Run log helpers for the Wi-Fi test runner."""
from __future__ import annotations

import io
import logging
import multiprocessing
import re
import sys
import tempfile
import threading
from contextlib import suppress
from pathlib import Path

from src.util.constants import Paths
from src.ui.view.theme import STYLE_BASE, TEXT_COLOR


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
        # ensure line breaks and progress signal capturing
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
        return False  # must return False here

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


