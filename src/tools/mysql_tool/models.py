from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnDefinition:
    name: str
    definition: str


@dataclass(frozen=True)
class HeaderMapping:
    original: str
    sanitized: str
