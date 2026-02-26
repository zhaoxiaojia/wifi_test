## Scope
- Applies to everything under `src/util/report/`.

## Goal
- Centralize all report- and Excel-related code here.
- Other modules should import functions/classes from this package instead of
  re-implementing Excel I/O, schemas, or formatting logic.

## Design Rules
- Prefer pure functions and small modules over large “god files”.
- Keep `pandas` usage for table-oriented plan files; use `openpyxl` for
  in-place workbook edits and for styled report generation.
- Avoid `DataFrame.to_excel()` for updating existing formatted templates; use
  `openpyxl` cell updates to preserve styles, formulas, data validation, etc.

## File Layout (Preferred)
- `excel_plan.py`: read/write test plan xlsx (schema: column names/constants).
- `excel_update.py`: update existing xlsx templates (e.g. by `TCID`).
- `performance_import.py`: parse performance workbooks into rows for DB import.
- `project_report.py`: generate the final project xlsx report (openpyxl + charts).
- `schemas.py`: shared sheet/column constants and validation helpers.

## Compatibility
- When moving code, keep thin import shims at the old paths until all callers
  are migrated (delete shims only after a repo-wide update).

