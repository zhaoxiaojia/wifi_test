from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ColumnDefinition:
    name: str
    definition: str


@dataclass(frozen=True)
class HeaderMapping:
    original: str
    sanitized: str


@dataclass(frozen=True)
class SyncResult:
    dut_id: int
    execution_id: int


@dataclass(frozen=True)
class TestResultContext:
    dut_id: int
    execution_id: int
    case_path: Optional[str]
    data_type: Optional[str]
    log_file_path: str
    run_source: str
