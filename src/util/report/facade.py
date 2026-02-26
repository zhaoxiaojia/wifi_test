"""Facade for project Excel report generation.

Callers should import :func:`generate_project_report` from this module.
Implementation details (builder/style) live in sibling modules so we can
iterate on formatting without touching callers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.util.report.builder import generate_project_report as _generate


def generate_project_report(
    result_file: str | Path,
    output: str | Path,
    *,
    forced_test_type: Optional[str] = None,
    sheet_name: str | None = None,
) -> None:
    return _generate(
        result_file,
        output,
        forced_test_type=forced_test_type,
        sheet_name=sheet_name,
    )


__all__ = ["generate_project_report"]
