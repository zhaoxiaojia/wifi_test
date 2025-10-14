from __future__ import annotations

import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .client import MySqlClient
from .models import HeaderMapping
from .naming import IdentifierBuilder
from .schema import read_csv_rows

__all__ = [
    "PerformanceTableManager",
    "sync_configuration",
    "sync_test_result_to_db",
    "sync_file_to_db",
]


@dataclass(frozen=True)
class _ColumnInfo:
    mapping: HeaderMapping
    sql_type: str


class PerformanceTableManager:
    """管理 `performance` 表：结构随 CSV 头动态重建，并完整同步行数据。"""

    TABLE_NAME = "performance"
    _BASE_COLUMNS: Tuple[Tuple[str, str], ...] = (
        ("csv_name", "VARCHAR(255) NOT NULL"),
        ("row_index", "INT NOT NULL"),
        ("data_type", "VARCHAR(64) NULL DEFAULT NULL"),
        ("run_source", "VARCHAR(32) NULL DEFAULT NULL"),
    )

    def __init__(self, client: MySqlClient) -> None:
        self._client = client

    @staticmethod
    def _classify_value(value: Any) -> Tuple[str, Any]:
        if value is None:
            return "empty", None
        if isinstance(value, (dict, list)):
            return "json", value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if isinstance(value, float) and not value.is_integer():
                return "float", float(value)
            return "int", int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return "empty", None
            lowered = stripped.lower()
            if lowered in {"null", "none", "nan"}:
                return "empty", None
            if stripped[0] in {"{", "["}:
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, (dict, list)):
                        return "json", parsed
                except Exception:
                    pass
            try:
                return "int", int(stripped)
            except Exception:
                pass
            try:
                return "float", float(stripped)
            except Exception:
                pass
            return "text", stripped
        return "text", str(value)

    @classmethod
    def _infer_sql_type(cls, values: Iterable[Any]) -> str:
        seen_float = False
        seen_int = False
        for value in values:
            value_type, _ = cls._classify_value(value)
            if value_type == "json":
                return "JSON"
            if value_type == "text":
                return "TEXT"
            if value_type == "float":
                seen_float = True
            elif value_type == "int":
                seen_int = True
        if seen_float:
            return "DOUBLE"
        if seen_int:
            return "BIGINT"
        return "TEXT"

    @staticmethod
    def _normalize_cell(value: Any, sql_type: str) -> Any:
        value_type, parsed = PerformanceTableManager._classify_value(value)
        if parsed is None:
            return None
        if sql_type == "JSON":
            if value_type in {"json", "float", "int"}:
                return json.dumps(parsed, ensure_ascii=False)
            return json.dumps(str(parsed), ensure_ascii=False)
        if sql_type == "DOUBLE":
            if value_type in {"float", "int"}:
                return float(parsed)
            return None
        if sql_type == "BIGINT":
            if value_type == "int":
                return int(parsed)
            if value_type == "float":
                float_value = float(parsed)
                if float_value.is_integer():
                    return int(float_value)
            return None
        return str(parsed)

    @staticmethod
    def _build_mappings(headers: Sequence[str]) -> List[HeaderMapping]:
        builder = IdentifierBuilder()
        reserved = {name for name, _ in PerformanceTableManager._BASE_COLUMNS}
        used = set(reserved)
        mappings: List[HeaderMapping] = []
        for header in headers:
            if not header:
                continue
            candidate = builder.build((header,), fallback="column")
            if candidate in used:
                candidate = builder.build((header, "field"), fallback="column")
            while candidate in used:
                candidate = builder.build((header, str(len(used))), fallback="column")
            used.add(candidate)
            mappings.append(HeaderMapping(original=header, sanitized=candidate))
        return mappings

    def _prepare_columns(
        self, mappings: Sequence[HeaderMapping], rows: Sequence[Dict[str, Any]]
    ) -> List[_ColumnInfo]:
        columns: List[_ColumnInfo] = []
        for mapping in mappings:
            values = [row.get(mapping.original) for row in rows]
            sql_type = self._infer_sql_type(values)
            columns.append(_ColumnInfo(mapping=mapping, sql_type=sql_type))
        return columns

    def _recreate_table(self, columns: Sequence[_ColumnInfo]) -> None:
        self._client.execute(f"DROP TABLE IF EXISTS `{self.TABLE_NAME}`")
        statements: List[str] = ["CREATE TABLE `performance` ("]
        statements.append("    `id` INT PRIMARY KEY AUTO_INCREMENT,")
        for name, definition in self._BASE_COLUMNS:
            statements.append(f"    `{name}` {definition},")
        for column in columns:
            definition = f"{column.sql_type} NULL DEFAULT NULL"
            comment = column.mapping.original.replace("'", "''")
            statements.append(
                f"    `{column.mapping.sanitized}` {definition} COMMENT '{comment}',"
            )
        statements.extend(
            [
                "    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,",
                "    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;",
            ]
        )
        create_sql = "\n".join(statements)
        self._client.execute(create_sql)

    def replace_with_csv(
        self,
        *,
        csv_name: str,
        headers: Sequence[str],
        rows: Sequence[Dict[str, Any]],
        data_type: Optional[str],
        run_source: str,
    ) -> int:
        """重建 `performance` 表结构并写入当前 CSV 的所有记录。"""

        logging.info(
            "Preparing to rebuild %s using CSV %s | headers=%s rows=%s",  # noqa: G004
            self.TABLE_NAME,
            csv_name,
            len(headers),
            len(rows),
        )

        mappings = self._build_mappings(headers)
        logging.debug(
            "Header mappings: %s",
            {mapping.original: mapping.sanitized for mapping in mappings},
        )

        column_infos = self._prepare_columns(mappings, rows)
        logging.info(
            "Recreating %s with %s dynamic columns", self.TABLE_NAME, len(column_infos)
        )
        self._recreate_table(column_infos)

        if not rows:
            logging.info(
                "CSV %s contains no rows; %s table recreated without data.",
                csv_name,
                self.TABLE_NAME,
            )
            return 0

        insert_columns = [name for name, _ in self._BASE_COLUMNS]
        insert_columns.extend(info.mapping.sanitized for info in column_infos)
        column_clause = ", ".join(f"`{name}`" for name in insert_columns)
        placeholders = ", ".join(["%s"] * len(insert_columns))
        insert_sql = (
            f"INSERT INTO `{self.TABLE_NAME}` ({column_clause}) VALUES ({placeholders})"
        )

        values: List[List[Any]] = []
        for index, row in enumerate(rows, start=1):
            row_values: List[Any] = [
                csv_name,
                index,
                data_type,
                run_source,
            ]
            for info in column_infos:
                row_values.append(
                    self._normalize_cell(row.get(info.mapping.original), info.sql_type)
                )
            values.append(row_values)

        affected_total = 0
        for row_values in values:
            logging.debug(
                "Inserting row %s/%s into %s",  # noqa: G004
                row_values[1],
                len(values),
                self.TABLE_NAME,
            )
            affected_total += self._client.execute(insert_sql, row_values)

        if affected_total != len(values):
            logging.warning(
                "Expected to insert %s rows but database reported %s",  # noqa: G004
                len(values),
                affected_total,
            )
        else:
            logging.info(
                "Stored %s rows from %s into %s",  # noqa: G004
                affected_total,
                csv_name,
                self.TABLE_NAME,
            )
        return affected_total


def sync_configuration(config: dict | None) -> None:
    """Kept for backward compatibility; configuration is no longer persisted."""

    if config:
        logging.debug("Configuration sync skipped; persistence has been removed.")
    return None


def sync_test_result_to_db(
    config: dict | None,
    *,
    log_file: str,
    data_type: Optional[str] = None,
    case_path: Optional[str] = None,
    run_source: str = "local",
) -> int:
    """Load the CSV file and mirror its rows into the performance table."""

    del config, case_path  # Unused but kept for signature compatibility.

    file_path = Path(log_file)
    if not file_path.is_file():
        logging.error("Log file %s not found, skip syncing test results.", log_file)
        return 0

    headers, rows = read_csv_rows(file_path)
    logging.info(
        "Loaded CSV %s | header_count=%s row_count=%s",  # noqa: G004
        file_path,
        len(headers),
        len(rows),
    )
    if not headers:
        logging.warning("CSV file %s does not contain a header row.", log_file)

    normalized_data_type = data_type.strip().upper() if isinstance(data_type, str) else None
    normalized_source = (run_source or "local").strip() or "local"
    normalized_source = normalized_source.upper()[:32]

    try:
        with MySqlClient() as client:
            manager = PerformanceTableManager(client)
            affected = manager.replace_with_csv(
                csv_name=file_path.name,
                headers=headers,
                rows=rows,
                data_type=normalized_data_type,
                run_source=normalized_source,
            )
        return affected
    except Exception:
        logging.exception("Failed to sync CSV results into performance table")
        return 0


def sync_file_to_db(
    file_path: str,
    data_type: str,
    *,
    config: Optional[dict] = None,
    case_path: Optional[str] = None,
    run_source: str = "FRAMEWORK",
) -> int:
    """Convenience wrapper mirroring :func:`sync_test_result_to_db`."""

    return sync_test_result_to_db(
        config or {},
        log_file=file_path,
        data_type=data_type,
        case_path=case_path,
        run_source=run_source,
    )
