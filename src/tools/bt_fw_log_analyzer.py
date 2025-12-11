"""Compatibility shim for BT FW log helpers.

Business logic now lives in ``src.tools.analyze.bt``; this module
re-exports its public helpers so existing imports continue to work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from src.tools.analyze.bt import analyze_bt_fw_log as _analyze_impl, capture_serial_log as _capture_impl


def analyze_bt_fw_log(
    log_path: str | Path,
    *,
    is_normal_mode: bool = True,
    add_timestamp: bool = True,
    on_chunk: Optional[Callable[[str], None]] = None,
    output_path: str | Path | None = None,
) -> str:
    return _analyze_impl(
        log_path,
        is_normal_mode=is_normal_mode,
        add_timestamp=add_timestamp,
        on_chunk=on_chunk,
        output_path=output_path,
    )


def capture_serial_log(
    port: str,
    baudrate: int,
    *,
    add_timestamp: bool = True,
    on_raw_text: Optional[Callable[[str], None]] = None,
    stop_flag: Optional[Callable[[], bool]] = None,
) -> list[Path]:
    return _capture_impl(
        port,
        baudrate,
        add_timestamp=add_timestamp,
        on_raw_text=on_raw_text,
        stop_flag=stop_flag,
    )


__all__ = ["analyze_bt_fw_log", "capture_serial_log"]
