"""Excel test-plan helpers.

This module is the single place that understands the plan Excel schema.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple, Union

import pandas as pd

from src.util.report.excel.common import ExcelTable
from src.util.report.excel.schemas import PLAN_COLS


def read_script_paths(path: Union[str, Path], include_test_type: bool = False) -> Union[
    List[str], Tuple[str, List[str]]]:
    df = pd.read_excel(path)

    if PLAN_COLS.SCRIPT_PATH not in df.columns:
        raise ValueError(f"Excel file must contain a '{PLAN_COLS.SCRIPT_PATH}' column.")

    script_paths = [str(v) for v in df[PLAN_COLS.SCRIPT_PATH].dropna().tolist()]

    if not include_test_type:
        return script_paths

    # 使用PLAN_COLS.TEST_TYPE常量
    test_type = "Classic"
    if PLAN_COLS.TEST_TYPE in df.columns:
        test_type_series = df[PLAN_COLS.TEST_TYPE].dropna()
        if not test_type_series.empty:
            test_type = str(test_type_series.iloc[0])

    return test_type, script_paths


def update_row_status(
    path: str | Path,
    *,
    row_index: int,
    status: str,
    sheet_name: str | None = None,
) -> None:
    """Update Status by 0-based row index (DataFrame row order).

    Uses openpyxl for in-place updates to preserve formatting.
    """

    if row_index < 0:
        raise ValueError("row_index must be >= 0")
    table = ExcelTable.open(path, sheet_name=sheet_name, required_columns=(PLAN_COLS.STATUS,))
    excel_row = table.data_first_row() + row_index
    table.set_cell(row=excel_row, column_name=PLAN_COLS.STATUS, value=str(status))
    table.save(path)


def write_plan(
    path: str | Path,
    *,
    rows: Sequence[dict],
    column_order: Sequence[str],
) -> None:
    df = pd.DataFrame(list(rows))
    df = df[list(column_order)]
    df.to_excel(path, index=False, engine="openpyxl")
