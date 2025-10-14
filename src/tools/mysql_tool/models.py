from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ColumnDefinition:
    name: str
    definition: str


@dataclass(frozen=True)
class HeaderMapping:
    original: str
    sanitized: str


@dataclass(frozen=True)
class TableIndex:
    name: str
    definition: str


@dataclass(frozen=True)
class TableConstraint:
    name: str
    definition: str


@dataclass(frozen=True)
class TableSpec:
    columns: Sequence[ColumnDefinition]
    indexes: Sequence[TableIndex] = tuple()
    constraints: Sequence[TableConstraint] = tuple()
    engine: str = "InnoDB"
    charset: str = "utf8mb4"
    include_audit_columns: bool = True
