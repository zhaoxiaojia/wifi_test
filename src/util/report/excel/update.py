"""In-place updates for result Excel files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.util.report.excel.common import ExcelTable
from src.util.report.excel.schemas import MAX_EXCEL_CELL_TEXT_LEN, PLAN_COLS


def update_test_result_by_tcid(
    excel_path: str | Path,
    *,
    tcid: str,
    final_status: str,
    step_details: str,
    sheet_name: Optional[str] = None,
) -> bool:
    """Update a test_result.xlsx-like file in place.

    Returns True if a matching TCID row is found and updated.
    """

    tcid_expected = (tcid or "").strip()
    if not tcid_expected:
        return False

    table = ExcelTable.open(
        excel_path,
        sheet_name=sheet_name,
        required_columns=(PLAN_COLS.TCID, PLAN_COLS.STATUS, PLAN_COLS.STEP_DETAILS),
    )
    row = table.find_first_row(column_name=PLAN_COLS.TCID, equals_text=tcid_expected)
    if row is None:
        return False
    table.set_cell(row=row, column_name=PLAN_COLS.STATUS, value=str(final_status))
    details = "" if step_details is None else str(step_details)
    table.set_cell(
        row=row,
        column_name=PLAN_COLS.STEP_DETAILS,
        value=details[:MAX_EXCEL_CELL_TEXT_LEN],
    )
    table.save(excel_path)
    return True
    return False
