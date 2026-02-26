"""Schemas and constants for Excel-based reporting.

Centralize sheet/column names so callers don't re-encode strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


MAX_EXCEL_CELL_TEXT_LEN: Final[int] = 32767


@dataclass(frozen=True)
class PlanColumns:
    """Columns used by plan-style Excel files."""

    TCID: str = "TCID"
    PRIORITY: str = "Priority"
    TAG: str = "Tag"
    MODULE: str = "Module"
    DESCRIPTION: str = "Description"
    SCRIPT_PATH: str = "Script Path"
    STATUS: str = "Status"
    STEP_DETAILS: str = "Step_Details"


PLAN_COLS: Final[PlanColumns] = PlanColumns()

