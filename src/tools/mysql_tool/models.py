from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ColumnDefinition:
    """
    Column definition.

    Parameters
    ----------
    None
        This class does not take constructor arguments beyond ``self``.

    Returns
    -------
    None
        This class does not return a value.
    """
    name: str
    definition: str


@dataclass(frozen=True)
class HeaderMapping:
    """
    Header mapping.

    Parameters
    ----------
    None
        This class does not take constructor arguments beyond ``self``.

    Returns
    -------
    None
        This class does not return a value.
    """
    original: str
    sanitized: str


@dataclass(frozen=True)
class TableIndex:
    """
    Table index.

    Parameters
    ----------
    None
        This class does not take constructor arguments beyond ``self``.

    Returns
    -------
    None
        This class does not return a value.
    """
    name: str
    definition: str


@dataclass(frozen=True)
class TableConstraint:
    """
    Table constraint.

    Parameters
    ----------
    None
        This class does not take constructor arguments beyond ``self``.

    Returns
    -------
    None
        This class does not return a value.
    """
    name: str
    definition: str


@dataclass(frozen=True)
class TableSpec:
    """
    Table spec.

    Parameters
    ----------
    None
        This class does not take constructor arguments beyond ``self``.

    Returns
    -------
    None
        This class does not return a value.
    """
    columns: Sequence[ColumnDefinition]
    indexes: Sequence[TableIndex] = tuple()
    constraints: Sequence[TableConstraint] = tuple()
    engine: str = "InnoDB"
    charset: str = "utf8mb4"
    include_audit_columns: bool = True
