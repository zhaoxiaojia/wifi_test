"""Runtime stdout/stderr tee for full-session logging.

This module is imported automatically by Python when present on the import
path. It installs a tee on ``sys.stdout`` and ``sys.stderr`` so that every
message printed during interpreter lifetime is mirrored into ``python_run.log``
under the repository root. The log path is exported via the
``PYTHON_RUN_ROOT_LOG`` environment variable for later reuse by pytest hooks.
"""
from __future__ import annotations

import atexit
import io
import os
import sys
import threading
from pathlib import Path
from typing import Optional

__all__ = [
    "flush_python_run_log",
    "get_python_run_log_path",
]

_LOG_ENV_KEY = "PYTHON_RUN_ROOT_LOG"
_TEE_ENABLED_FLAG = "PYTHON_RUN_LOG_TEE_ENABLED"

_log_file: Optional[io.TextIOWrapper] = None
_original_streams: dict[str, io.TextIOBase] = {}
_stream_lock = threading.RLock()


def _create_log_file() -> io.TextIOWrapper:
    """Create (or truncate) the root-level run log file."""
    root_dir = Path(__file__).resolve().parent
    log_path = root_dir / "python_run.log"
    log_file = log_path.open(mode="w", encoding="utf-8", buffering=1)
    os.environ[_LOG_ENV_KEY] = str(log_path)
    return log_file


class _StreamTee(io.TextIOBase):
    """Mirror writes to both the original stream and the log file."""

    def __init__(self, original: io.TextIOBase, log: io.TextIOWrapper) -> None:
        self._original = original
        self._log = log
        self._lock = threading.RLock()

    def write(self, data: str) -> int:  # type: ignore[override]
        if not data:
            return 0
        with self._lock:
            written = self._original.write(data)
            self._log.write(data)
            return written

    @property
    def encoding(self) -> str:
        return getattr(self._original, "encoding", "utf-8")

    @property
    def errors(self) -> str:
        return getattr(self._original, "errors", "strict")

    def flush(self) -> None:  # type: ignore[override]
        with self._lock:
            self._original.flush()
            self._log.flush()

    def isatty(self) -> bool:  # type: ignore[override]
        return self._original.isatty()

    def fileno(self) -> int:  # type: ignore[override]
        return self._original.fileno()

    def close(self) -> None:  # type: ignore[override]
        with self._lock:
            try:
                self._original.flush()
            finally:
                self._log.flush()


def _restore_streams(close_log: bool = True) -> None:
    """Restore original streams and close the log file if requested."""
    global _log_file
    if not _original_streams:
        return
    for name, stream in list(_original_streams.items()):
        setattr(sys, name, stream)
    _original_streams.clear()
    if close_log and _log_file is not None:
        try:
            _log_file.flush()
            _log_file.close()
        finally:
            _log_file = None
    os.environ.pop(_TEE_ENABLED_FLAG, None)


def _install_tee() -> None:
    """Install the tee once per interpreter session."""
    global _log_file
    if os.environ.get(_TEE_ENABLED_FLAG) == "1":
        return
    log_file = _create_log_file()
    _log_file = log_file
    for attr in ("stdout", "stderr"):
        original = getattr(sys, attr)
        _original_streams[attr] = original
        setattr(sys, attr, _StreamTee(original, log_file))
    os.environ[_TEE_ENABLED_FLAG] = "1"
    atexit.register(_restore_streams)


def flush_python_run_log() -> None:
    """Flush buffered data into the python_run.log file."""
    if _log_file is not None:
        with _stream_lock:
            _log_file.flush()


def get_python_run_log_path() -> Optional[Path]:
    """Return the path to the python_run.log file if available."""
    path = os.environ.get(_LOG_ENV_KEY)
    if not path:
        return None
    return Path(path)


_install_tee()
