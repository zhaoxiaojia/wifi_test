#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/15 15:22
# @Author  : chao.li
# @File    : MySqlControl.py

import csv
import json
import logging
import re
import sys
import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pymysql
from pymysql.cursors import DictCursor

BASE_DIR = Path(__file__).resolve().parents[3]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.tools.config_sections import split_config_data


def _load_mysql_config() -> Dict[str, Any]:
    """Return MySQL connection parameters loaded from tool_config.yaml."""
    config_path = BASE_DIR / "config" / "tool_config.yaml"
    try:
        with config_path.open(encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        logging.error("tool_config.yaml not found at %s", config_path)
        return {}
    except Exception as exc:
        logging.error("Failed to read tool_config.yaml: %s", exc)
        return {}
    mysql_cfg = config.get("mysql") or {}
    params = {
        "host": mysql_cfg.get("host"),
        "port": int(mysql_cfg.get("port", 3306)) if mysql_cfg.get("port") else 3306,
        "user": str(mysql_cfg.get("user")) if mysql_cfg.get("user") is not None else None,
        "password": str(mysql_cfg.get("passwd")) if mysql_cfg.get("passwd") is not None else None,
        "database": mysql_cfg.get("database"),
        "charset": mysql_cfg.get("charset", "utf8mb4"),
    }
    missing_keys = [key for key in ("host", "user", "password", "database") if not params.get(key)]
    if missing_keys:
        logging.error("Missing MySQL keys in tool_config.yaml: %s", ", ".join(missing_keys))
        return {}
    logging.debug("Loaded MySQL config from tool_config.yaml: %s", params)
    return params


def _ensure_database_exists(config: Dict[str, Any]) -> None:
    db_name = config.get("database")
    if not db_name:
        raise RuntimeError("Database name is missing in mysql config.")
    connection = pymysql.connect(
        host=config.get("host"),
        port=int(config.get("port", 3306)),
        user=config.get("user"),
        password=config.get("password"),
        charset=config.get("charset", "utf8mb4"),
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()


_IDENTIFIER_RE = re.compile(r"[^0-9a-zA-Z]+")


@dataclass(frozen=True)
class ColumnDefinition:
    name: str
    definition: str


@dataclass(frozen=True)
class HeaderMapping:
    original: str
    sanitized: str


@dataclass(frozen=True)
class SyncResult:
    dut_id: int
    execution_id: int


@dataclass(frozen=True)
class TestResultContext:
    dut_id: int
    execution_id: int
    case_path: Optional[str]
    data_type: Optional[str]
    log_file_path: str


class IdentifierBuilder:
    """生成唯一且符合 SQL 规范的列名。"""

    def __init__(self) -> None:
        self._counts: Dict[str, int] = {}

    def build(self, parts: Sequence[str], *, fallback: str = "field") -> str:
        sanitized_parts: List[str] = []
        for part in parts:
            sanitized = _IDENTIFIER_RE.sub("_", str(part).strip())
            sanitized = sanitized.strip("_").lower()
            if not sanitized:
                sanitized = fallback
            if sanitized[0].isdigit():
                sanitized = f"f_{sanitized}"
            sanitized_parts.append(sanitized)
        base = "_".join(sanitized_parts) if sanitized_parts else fallback
        if not base:
            base = fallback
        count = self._counts.get(base, 0)
        self._counts[base] = count + 1
        if count:
            return f"{base}_{count}"
        return base


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


def _build_section_payload(
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


def _sanitize_single_identifier(value: str, *, fallback: str) -> str:
    sanitized = _IDENTIFIER_RE.sub("_", value.strip())
    sanitized = sanitized.strip("_").lower()
    if not sanitized:
        sanitized = fallback
    if sanitized[0].isdigit():
        prefix = fallback[0] if fallback else "t"
        sanitized = f"{prefix}_{sanitized}"
    return sanitized


def _resolve_case_table_name(
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
    return _sanitize_single_identifier(candidate, fallback="test_results")


def _drop_and_create_table(
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


def _insert_rows(
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


def _read_csv_rows(file_path: Path) -> Tuple[List[str], List[Dict[str, Any]]]:
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


def _build_header_mappings(headers: Sequence[str]) -> List[HeaderMapping]:
    builder = IdentifierBuilder()
    mappings: List[HeaderMapping] = []
    for header in headers:
        mappings.append(HeaderMapping(header, builder.build((header,), fallback="column")))
    return mappings


class MySqlClient:
    """Thin wrapper around pymysql with helpers for schema operations."""

    def __init__(self, *, autocommit: bool = False):
        self._connection: Optional[pymysql.connections.Connection] = None
        self._config = _load_mysql_config()
        if not self._config or not self._config.get("host"):
            raise RuntimeError("Missing MySQL connection parameters.")
        _ensure_database_exists(self._config)
        self._connection = pymysql.connect(
            host=self._config.get("host"),
            port=int(self._config.get("port", 3306)),
            user=self._config.get("user"),
            password=self._config.get("password"),
            database=self._config.get("database"),
            charset=self._config.get("charset", "utf8mb4"),
            autocommit=autocommit,
            cursorclass=DictCursor,
        )

    @property
    def connection(self):
        return self._connection

    def execute(self, sql: str, args: Optional[Sequence[Any]] = None) -> int:
        logging.debug("Execute SQL: %s | args: %s", sql, args)
        try:
            with self._connection.cursor() as cursor:
                affected = cursor.execute(sql, args)
            if not self._connection.get_autocommit():
                self._connection.commit()
            return affected
        except Exception as exc:
            if not self._connection.get_autocommit():
                self._connection.rollback()
            logging.error("SQL execution failed: %s", exc)
            raise

    def executemany(self, sql: str, args_list: Iterable[Sequence[Any]]) -> int:
        logging.debug("Execute many SQL: %s", sql)
        try:
            with self._connection.cursor() as cursor:
                affected = cursor.executemany(sql, args_list)
            if not self._connection.get_autocommit():
                self._connection.commit()
            return affected
        except Exception as exc:
            if not self._connection.get_autocommit():
                self._connection.rollback()
            logging.error("SQL executemany failed: %s", exc)
            raise

    def insert(self, sql: str, args: Optional[Sequence[Any]] = None) -> int:
        logging.debug("Insert SQL: %s | args: %s", sql, args)
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(sql, args)
                last_id = cursor.lastrowid
            if not self._connection.get_autocommit():
                self._connection.commit()
            return int(last_id or 0)
        except Exception as exc:
            if not self._connection.get_autocommit():
                self._connection.rollback()
            logging.error("SQL insert failed: %s", exc)
            raise

    def query_one(self, sql: str, args: Optional[Sequence[Any]] = None) -> Optional[Dict[str, Any]]:
        logging.debug("Query one SQL: %s | args: %s", sql, args)
        with self._connection.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchone()

    def query_all(self, sql: str, args: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        logging.debug("Query all SQL: %s | args: %s", sql, args)
        with self._connection.cursor() as cursor:
            cursor.execute(sql, args)
            rows = cursor.fetchall()
        return list(rows)

    def commit(self) -> None:
        if self._connection and not self._connection.get_autocommit():
            self._connection.commit()

    def rollback(self) -> None:
        if self._connection and not self._connection.get_autocommit():
            self._connection.rollback()

    def close(self) -> None:
        conn = getattr(self, "_connection", None)
        if conn:
            conn.close()
            self._connection = None

    def __enter__(self) -> "MySqlClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc:
            self.rollback()
        self.close()

    def __del__(self):  # pragma: no cover
        try:
            self.close()
        except Exception:
            pass


class ConfigSchemaSynchronizer:
    """根据配置动态同步 DUT 与 Execution 表结构及数据。"""

    DUT_TABLE = "dut_settings"
    EXECUTION_TABLE = "execution_settings"

    def __init__(self, client: MySqlClient) -> None:
        self._client = client

    def sync(self, config: dict) -> SyncResult:
        dut_section, execution_section = split_config_data(config)
        dut_columns, dut_values, dut_mapping = _build_section_payload(dut_section)
        execution_columns, execution_values, execution_mapping = _build_section_payload(execution_section)

        dut_id = self._create_table_and_insert(
            self.DUT_TABLE, dut_columns, dut_values, dut_mapping
        )
        execution_columns.insert(0, ColumnDefinition("dut_id", "INT NOT NULL"))
        execution_values.insert(0, dut_id)
        execution_mapping["dut_id"] = "dut.id"
        execution_id = self._create_table_and_insert(
            self.EXECUTION_TABLE, execution_columns, execution_values, execution_mapping
        )
        return SyncResult(dut_id=dut_id, execution_id=execution_id)

    def _create_table_and_insert(
        self,
        table_name: str,
        columns: Sequence[ColumnDefinition],
        values: Sequence[Any],
        mapping: Dict[str, str],
    ) -> int:
        _drop_and_create_table(self._client, table_name, columns)
        if mapping:
            logging.debug("%s column mapping: %s", table_name, mapping)
        inserted_ids = _insert_rows(self._client, table_name, columns, [values])
        if not inserted_ids:
            raise RuntimeError(f"Failed to insert row into {table_name}")
        return inserted_ids[0]


class TestResultTableManager:
    """负责针对测试用例目录创建结果表并写入日志数据。"""

    BASE_COLUMNS: Tuple[ColumnDefinition, ...] = (
        ColumnDefinition("dut_id", "INT NOT NULL"),
        ColumnDefinition("execution_id", "INT NOT NULL"),
        ColumnDefinition("case_path", "TEXT NULL DEFAULT NULL"),
        ColumnDefinition("data_type", "VARCHAR(64) NULL DEFAULT NULL"),
        ColumnDefinition("log_file_path", "TEXT NULL DEFAULT NULL"),
        ColumnDefinition("row_index", "INT NOT NULL"),
    )

    def __init__(self, client: MySqlClient) -> None:
        self._client = client

    def store_results(
        self,
        table_name: str,
        headers: Sequence[str],
        rows: Sequence[Dict[str, Any]],
        context: TestResultContext,
    ) -> int:
        header_mappings = _build_header_mappings(headers)
        logging.debug(
            "%s header mapping: %s",
            table_name,
            {mapping.sanitized: mapping.original for mapping in header_mappings},
        )
        columns = list(self.BASE_COLUMNS) + [
            ColumnDefinition(mapping.sanitized, "TEXT NULL DEFAULT NULL")
            for mapping in header_mappings
        ]
        _drop_and_create_table(self._client, table_name, columns)

        insert_columns = [column.name for column in columns]
        placeholders = ", ".join(["%s"] * len(insert_columns))
        sql = (
            f"INSERT INTO `{table_name}` ("
            f"{', '.join(f'`{name}`' for name in insert_columns)}) "
            f"VALUES ({placeholders})"
        )
        if not rows:
            logging.info(
                "No rows parsed from %s, skip inserting into %s",
                context.log_file_path,
                table_name,
            )
            return 0

        values_list: List[List[Any]] = []
        for index, row in enumerate(rows, start=1):
            row_values: List[Any] = [
                context.dut_id,
                context.execution_id,
                context.case_path,
                context.data_type.upper() if context.data_type else None,
                context.log_file_path,
                index,
            ]
            for mapping in header_mappings:
                value = row.get(mapping.original)
                if value is None:
                    row_values.append(None)
                else:
                    text = str(value).strip()
                    row_values.append(text if text else None)
            values_list.append(row_values)

        affected = self._client.executemany(sql, values_list)
        logging.info("Stored %s rows into %s", affected, table_name)
        return affected


_LATEST_SYNC_RESULT: Optional[SyncResult] = None


def sync_configuration(config: dict | None) -> Optional[SyncResult]:
    """同步 DUT / Execution 配置至数据库，返回对应的主键 ID。"""

    global _LATEST_SYNC_RESULT
    if not isinstance(config, dict) or not config:
        logging.debug("skip sync_configuration: empty config")
        return None
    try:
        with MySqlClient() as client:
            synchronizer = ConfigSchemaSynchronizer(client)
            result = synchronizer.sync(config)
        _LATEST_SYNC_RESULT = result
        logging.info(
            "Synchronized configuration to database (dut_id=%s, execution_id=%s)",
            result.dut_id,
            result.execution_id,
        )
        return result
    except Exception:
        logging.exception("Failed to sync configuration to database")
        return None


def sync_test_result_to_db(
    config: dict | None,
    *,
    log_file: str,
    data_type: Optional[str] = None,
    case_path: Optional[str] = None,
) -> int:
    """将性能测试日志写入按目录划分的结果表。"""

    config = config or {}
    sync_result = sync_configuration(config)
    if sync_result is None:
        logging.warning("Skip syncing test results because configuration sync failed.")
        return 0

    file_path = Path(log_file)
    if not file_path.is_file():
        logging.error("Log file %s not found, skip syncing test results.", log_file)
        return 0

    headers, rows = _read_csv_rows(file_path)
    if not headers:
        logging.warning("CSV file %s does not contain a header row, skip syncing.", log_file)
        return 0

    target_case_path = case_path or config.get("text_case")
    table_name = _resolve_case_table_name(target_case_path, data_type)
    context = TestResultContext(
        dut_id=sync_result.dut_id,
        execution_id=sync_result.execution_id,
        case_path=target_case_path,
        data_type=data_type,
        log_file_path=file_path.resolve().as_posix(),
    )

    try:
        with MySqlClient() as client:
            manager = TestResultTableManager(client)
            affected = manager.store_results(table_name, headers, rows, context)
        return affected
    except Exception:
        logging.exception("Failed to sync test results into table %s", table_name)
        return 0


def sync_file_to_db(
    file_path: str,
    data_type: str,
    *,
    config: Optional[dict] = None,
    case_path: Optional[str] = None,
) -> int:
    """兼容旧入口的数据库写入接口。"""

    resolved_config = config
    if resolved_config is None:
        try:
            from src.tools.config_loader import load_config  # 延迟导入避免循环依赖
        except Exception:
            logging.exception("Failed to import load_config for database sync")
            resolved_config = {}
        else:
            try:
                resolved_config = load_config(refresh=True)
            except Exception:
                logging.exception("Failed to load configuration for database sync")
                resolved_config = {}

    return sync_test_result_to_db(
        resolved_config or {},
        log_file=file_path,
        data_type=data_type,
        case_path=case_path,
    )


__all__ = [
    "MySqlClient",
    "sync_configuration",
    "sync_test_result_to_db",
    "sync_file_to_db",
]
