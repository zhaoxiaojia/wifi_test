from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, TYPE_CHECKING

from .models import ColumnDefinition, HeaderMapping
from .naming import IdentifierBuilder, sanitize_identifier

if TYPE_CHECKING:  # pragma: no cover
    from .client import MySqlClient

__all__ = [
    "build_section_payload",
    "build_header_mappings",
    "drop_and_create_table",
    "insert_rows",
    "read_csv_rows",
    "resolve_case_table_name",
]


def _flatten_section(
    data: Any, builder: IdentifierBuilder, prefix: Tuple[str, ...] = ()
) -> List[Tuple[str, Any, str]]:
    if isinstance(data, dict):
        items: List[Tuple[str, Any, str]] = []
        for key, value in data.items():
            items.extend(_flatten_section(value, builder, prefix + (str(key),)))
        return items
    path = ".".join(prefix) if prefix else "value"
    column_name = builder.build(prefix or ("value",), fallback="field")
    return [(column_name, data, path)]


def _infer_sql_type(value: Any) -> str:
    if isinstance(value, bool):
        return "TINYINT(1)"
    if isinstance(value, int) and not isinstance(value, bool):
        return "BIGINT"
    if isinstance(value, float):
        return "DOUBLE"
    if isinstance(value, (list, tuple, dict)):
        return "JSON"
    return "TEXT"


def _normalize_value(value: Any, sql_type: str) -> Any:
    if value is None:
        return None
    if sql_type == "TINYINT(1)":
        return 1 if bool(value) else 0
    if sql_type == "BIGINT":
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if sql_type == "DOUBLE":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if sql_type == "JSON":
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_section_payload(
    section: dict | None,
) -> Tuple[List[ColumnDefinition], List[Any], Dict[str, str]]:
    if not isinstance(section, dict) or not section:
        return [], [], {}

    builder = IdentifierBuilder()
    flattened = _flatten_section(section, builder)
    columns: List[ColumnDefinition] = []
    values: List[Any] = []
    mapping: Dict[str, str] = {}

    for column_name, raw_value, path in flattened:
        sql_type = _infer_sql_type(raw_value)
        columns.append(ColumnDefinition(column_name, f"{sql_type} NULL DEFAULT NULL"))
        values.append(_normalize_value(raw_value, sql_type))
        mapping[column_name] = path
    return columns, values, mapping


def resolve_case_table_name(
    case_path: Optional[str], data_type: Optional[str]
) -> str:
    candidate = None
    if case_path:
        path = Path(case_path)
        candidate = path.parent.name or path.stem
    if not candidate and data_type:
        candidate = data_type
    if not candidate:
        candidate = "test_results"
    return sanitize_identifier(candidate, fallback="test_results")


def drop_and_create_table(
    client: "MySqlClient", table_name: str, columns: Sequence[ColumnDefinition]
) -> None:
    client.execute(f"DROP TABLE IF EXISTS `{table_name}`")
    column_lines = [f"`{column.name}` {column.definition}" for column in columns]
    statements = [
        f"CREATE TABLE `{table_name}` (",
        "    id INT PRIMARY KEY AUTO_INCREMENT,",
    ]
    statements.extend(f"    {line}," for line in column_lines)
    statements.extend(
        [
            "    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,",
            "    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;",
        ]
    )
    create_sql = "\n".join(statements)
    client.execute(create_sql)


def insert_rows(
    client: "MySqlClient",
    table_name: str,
    columns: Sequence[ColumnDefinition],
    rows: Sequence[Sequence[Any]],
) -> List[int]:
    if not rows:
        return []
    if not columns:
        return [client.insert(f"INSERT INTO `{table_name}` () VALUES ()") for _ in rows]
    column_names = ", ".join(f"`{column.name}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO `{table_name}` ({column_names}) VALUES ({placeholders})"
    return [client.insert(sql, row) for row in rows]


def read_csv_rows(file_path: Path) -> Tuple[List[str], List[Dict[str, Any]]]:
    encodings = ("utf-8-sig", "gbk", "utf-8")
    for encoding in encodings:
        try:
            with file_path.open(encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                headers = reader.fieldnames or []
                rows = [dict(row) for row in reader]
                if headers:
                    return headers, rows
        except UnicodeDecodeError:
            continue
    with file_path.open(encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        rows = [dict(row) for row in reader]
    return headers, rows


def build_header_mappings(headers: Sequence[str]) -> List[HeaderMapping]:
    builder = IdentifierBuilder()
    mappings: List[HeaderMapping] = []
    for header in headers:
        mappings.append(HeaderMapping(header, builder.build((header,), fallback="column")))
    return mappings
