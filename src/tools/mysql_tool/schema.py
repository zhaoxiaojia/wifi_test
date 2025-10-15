from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, TYPE_CHECKING

from .models import (
    ColumnDefinition,
    HeaderMapping,
    TableConstraint,
    TableIndex,
    TableSpec,
)
from .naming import IdentifierBuilder, sanitize_identifier

if TYPE_CHECKING:  # pragma: no cover
    from .client import MySqlClient

__all__ = [
    "build_section_payload",
    "build_header_mappings",
    "insert_rows",
    "read_csv_rows",
    "resolve_case_table_name",
    "ensure_table",
    "ensure_config_tables",
    "ensure_report_tables",
    "PERFORMANCE_STATIC_COLUMNS",
]


PERFORMANCE_STATIC_COLUMNS: Tuple[Tuple[str, str, str], ...] = (
    ("serialnumber", "VARCHAR(255)", "SerianNumber"),
    ("test_category", "VARCHAR(255)", "Test_Category"),
    ("standard", "VARCHAR(255)", "Standard"),
    ("freq_band", "VARCHAR(255)", "Freq_Band"),
    ("bw", "VARCHAR(255)", "BW"),
    ("data_rate", "VARCHAR(255)", "Data_Rate"),
    ("ch_freq_mhz", "VARCHAR(255)", "CH_Freq_MHz"),
    ("protocol", "VARCHAR(255)", "Protocol"),
    ("direction", "VARCHAR(255)", "Direction"),
    ("total_path_loss", "VARCHAR(255)", "Total_Path_Loss"),
    ("db", "DOUBLE", "DB"),
    ("rssi", "DOUBLE", "RSSI"),
    ("angel", "VARCHAR(255)", "Angel"),
    ("mcs_rate", "VARCHAR(255)", "MCS_Rate"),
    ("throughput", "DOUBLE", "Throughput"),
    ("expect_rate", "DOUBLE", "Expect_Rate"),
)

_AUDIT_COLUMNS: Tuple[ColumnDefinition, ...] = (
    ColumnDefinition("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ColumnDefinition(
        "updated_at",
        "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    ),
)

_PERFORMANCE_BASE_COLUMNS: Tuple[ColumnDefinition, ...] = (
    ColumnDefinition("test_report_id", "INT NOT NULL"),
    ColumnDefinition("csv_name", "VARCHAR(255) NOT NULL"),
    ColumnDefinition("data_type", "VARCHAR(64)"),
)

def _build_performance_definition(definition: str, comment: str) -> str:
    escaped = comment.replace("'", "''")
    return f"{definition} NULL DEFAULT NULL COMMENT '{escaped}'"


_PERFORMANCE_EXTRA_COLUMNS: Tuple[ColumnDefinition, ...] = tuple(
    ColumnDefinition(name, _build_performance_definition(definition, comment))
    for name, definition, comment in PERFORMANCE_STATIC_COLUMNS
)


_TABLE_SPECS: Dict[str, TableSpec] = {
    "dut": TableSpec(
        columns=(
            ColumnDefinition("software_version", "VARCHAR(128)"),
            ColumnDefinition("driver_version", "VARCHAR(128)"),
            ColumnDefinition("hardware_version", "VARCHAR(128)"),
            ColumnDefinition("android_version", "VARCHAR(64)"),
            ColumnDefinition("kernel_version", "VARCHAR(64)"),
            ColumnDefinition("connect_type", "VARCHAR(64)"),
            ColumnDefinition("adb_device", "VARCHAR(128)"),
            ColumnDefinition("telnet_ip", "VARCHAR(128)"),
            ColumnDefinition("product_line", "VARCHAR(64)"),
            ColumnDefinition("project", "VARCHAR(64)"),
            ColumnDefinition("main_chip", "VARCHAR(64)"),
            ColumnDefinition("wifi_module", "VARCHAR(64)"),
            ColumnDefinition("interface", "VARCHAR(64)"),
        ),
        include_audit_columns=False,
    ),
    "execution": TableSpec(
        columns=(
            ColumnDefinition("case_path", "VARCHAR(512)"),
            ColumnDefinition("case_root", "VARCHAR(128)"),
            ColumnDefinition("router_name", "VARCHAR(128)"),
            ColumnDefinition("router_address", "VARCHAR(128)"),
            ColumnDefinition("rf_model", "VARCHAR(128)"),
            ColumnDefinition("corner_model", "VARCHAR(128)"),
            ColumnDefinition("lab_name", "VARCHAR(128)"),
        ),
        include_audit_columns=False,
    ),
    "test_report": TableSpec(
        columns=(
            ColumnDefinition("execution_id", "INT NULL DEFAULT NULL"),
            ColumnDefinition("dut_id", "INT NULL DEFAULT NULL"),
            ColumnDefinition("csv_name", "VARCHAR(255) NOT NULL"),
            ColumnDefinition("csv_path", "VARCHAR(512)"),
            ColumnDefinition("data_type", "VARCHAR(64)"),
            ColumnDefinition("case_path", "VARCHAR(512)"),
        ),
        indexes=(
            TableIndex(
                "idx_test_report_execution", "INDEX idx_test_report_execution (`execution_id`)"
            ),
            TableIndex(
                "idx_test_report_dut", "INDEX idx_test_report_dut (`dut_id`)"
            ),
        ),
        constraints=(
            TableConstraint(
                "fk_test_report_execution",
                "CONSTRAINT fk_test_report_execution FOREIGN KEY (`execution_id`) REFERENCES `execution`(`id`) ON DELETE SET NULL",
            ),
            TableConstraint(
                "fk_test_report_dut",
                "CONSTRAINT fk_test_report_dut FOREIGN KEY (`dut_id`) REFERENCES `dut`(`id`) ON DELETE SET NULL",
            ),
        ),
    ),
    "performance": TableSpec(
        columns=_PERFORMANCE_BASE_COLUMNS + _PERFORMANCE_EXTRA_COLUMNS,
        indexes=(
            TableIndex(
                "idx_performance_report", "INDEX idx_performance_report (`test_report_id`)"
            ),
        ),
        constraints=(
            TableConstraint(
                "fk_performance_report",
                "CONSTRAINT fk_performance_report FOREIGN KEY (`test_report_id`) REFERENCES `test_report`(`id`) ON DELETE CASCADE",
            ),
        ),
    ),
}


def ensure_table(client, table_name: str, spec: TableSpec) -> None:
    if _table_exists(client, table_name):
        return
    _create_table(client, table_name, spec)


def ensure_config_tables(client) -> None:
    ensure_table(client, "dut", _TABLE_SPECS["dut"])
    ensure_table(client, "execution", _TABLE_SPECS["execution"])


def ensure_report_tables(client) -> None:
    ensure_config_tables(client)
    ensure_table(client, "test_report", _TABLE_SPECS["test_report"])
    ensure_table(client, "performance", _TABLE_SPECS["performance"])

def _table_exists(client, table_name: str) -> bool:
    try:
        rows = client.query_all("SHOW TABLES LIKE %s", (table_name,))
    except Exception:
        logging.debug("Failed to inspect table %s", table_name, exc_info=True)
        return False
    return bool(rows)


def _create_table(client, table_name: str, spec: TableSpec) -> None:
    all_columns = [ColumnDefinition("id", "INT PRIMARY KEY AUTO_INCREMENT")]
    all_columns.extend(spec.columns)
    if spec.include_audit_columns:
        all_columns.extend(_AUDIT_COLUMNS)
    column_lines = [f"`{column.name}` {column.definition}" for column in all_columns]
    extra_lines = [item.definition for item in spec.indexes] + [
        item.definition for item in spec.constraints
    ]
    lines = column_lines + extra_lines
    statement = (
        f"CREATE TABLE `{table_name}` (\n    "
        + ",\n    ".join(lines)
        + f"\n) ENGINE={spec.engine} DEFAULT CHARSET={spec.charset};"
    )
    client.execute(statement)


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
    case_path: Optional[str],
    data_type: Optional[str],
    *,
    log_file_path: Optional[Path] = None,
) -> str:
    candidate = None
    if case_path:
        path = Path(case_path)
        candidate = path.parent.name or path.stem
    if not candidate and data_type:
        candidate = data_type
    if not candidate:
        candidate = "test_results"

    base = sanitize_identifier(candidate, fallback="test_results")

    if not log_file_path:
        return base

    stem = sanitize_identifier(log_file_path.stem, fallback="result")
    if not stem or stem == base:
        return base
    return f"{base}_{stem}"


def drop_and_create_table(
    client: "MySqlClient", table_name: str, columns: Sequence[ColumnDefinition]
) -> None:
    client.execute(f"DROP TABLE IF EXISTS `{table_name}`")
    statements = [
        f"CREATE TABLE `{table_name}` (",
        "    id INT PRIMARY KEY AUTO_INCREMENT,",
    ]
    statements.extend(f"    {line}," for line in column_lines)
    if spec.include_audit_columns:
        statements.extend(
            [
                "    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,",
                "    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
            ]
        )
    statements.append(f") ENGINE={spec.engine} DEFAULT CHARSET={spec.charset};")
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
