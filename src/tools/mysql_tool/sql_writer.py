"""Small SQL string builder helpers shared by MySQL tooling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SqlWriter:
    """Compose common SQL snippets such as INSERT statements."""

    table_name: str

    def column_clause(self, columns: Sequence[str]) -> str:
        """Return a comma-joined list of backticked column names."""
        return ", ".join(f"`{name}`" for name in columns)

    def placeholders(self, count: int) -> str:
        """Return a placeholder clause sized for the provided column count."""
        return ", ".join(["%s"] * count)

    def insert_statement(self, columns: Sequence[str]) -> str:
        """Return a simple INSERT statement for the configured table."""
        return (
            f"INSERT INTO `{self.table_name}` "
            f"({self.column_clause(columns)}) VALUES ({self.placeholders(len(columns))})"
        )
