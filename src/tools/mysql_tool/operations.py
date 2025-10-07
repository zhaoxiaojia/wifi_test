from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .client import MySqlClient
from .models import ColumnDefinition, SyncResult, TestResultContext
from .schema import (
    build_header_mappings,
    build_section_payload,
    drop_and_create_table,
    insert_rows,
    read_csv_rows,
    resolve_case_table_name,
)

_LATEST_SYNC_RESULT: Optional[SyncResult] = None

__all__ = [
    "ConfigSchemaSynchronizer",
    "TestResultTableManager",
    "sync_configuration",
    "sync_test_result_to_db",
    "sync_file_to_db",
]


class ConfigSchemaSynchronizer:
    """Synchronize DUT / Execution configuration sections into the database."""

    DUT_TABLE = "dut_settings"
    EXECUTION_TABLE = "execution_settings"

    def __init__(self, client: MySqlClient) -> None:
        self._client = client

    def sync(self, config: dict) -> SyncResult:
        from src.tools.config_sections import split_config_data  # local import to avoid cycle

        dut_section, execution_section = split_config_data(config)
        dut_columns, dut_values, dut_mapping = build_section_payload(dut_section)
        execution_columns, execution_values, execution_mapping = build_section_payload(execution_section)

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
        drop_and_create_table(self._client, table_name, columns)
        if mapping:
            logging.debug("%s column mapping: %s", table_name, mapping)
        inserted_ids = insert_rows(self._client, table_name, columns, [values])
        if not inserted_ids:
            raise RuntimeError(f"Failed to insert row into {table_name}")
        return inserted_ids[0]


class TestResultTableManager:
    """Persist parsed CSV results into case-specific tables."""

    BASE_COLUMNS: Sequence[ColumnDefinition] = (
        ColumnDefinition("dut_id", "INT NOT NULL"),
        ColumnDefinition("execution_id", "INT NOT NULL"),
        ColumnDefinition("case_path", "TEXT NULL DEFAULT NULL"),
        ColumnDefinition("data_type", "VARCHAR(64) NULL DEFAULT NULL"),
        ColumnDefinition("log_file_path", "TEXT NULL DEFAULT NULL"),
        ColumnDefinition("run_source", "VARCHAR(32) NOT NULL"),
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
        header_mappings = build_header_mappings(headers)
        logging.debug(
            "%s header mapping: %s",
            table_name,
            {mapping.sanitized: mapping.original for mapping in header_mappings},
        )
        columns = list(self.BASE_COLUMNS) + [
            ColumnDefinition(mapping.sanitized, "TEXT NULL DEFAULT NULL")
            for mapping in header_mappings
        ]
        drop_and_create_table(self._client, table_name, columns)

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
                context.run_source,
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


def sync_configuration(config: dict | None) -> Optional[SyncResult]:
    """Synchronize DUT / Execution configuration and store latest ids globally."""

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
    run_source: str = "local",
) -> int:
    """Persist parsed CSV log file results into a dynamically created table."""

    config = config or {}
    sync_result = sync_configuration(config)
    if sync_result is None:
        logging.warning("Skip syncing test results because configuration sync failed.")
        return 0

    normalized_source = (run_source or "local").strip() or "local"
    run_source = normalized_source[:32].upper()

    file_path = Path(log_file)
    if not file_path.is_file():
        logging.error("Log file %s not found, skip syncing test results.", log_file)
        return 0

    headers, rows = read_csv_rows(file_path)
    if not headers:
        logging.warning("CSV file %s does not contain a header row, skip syncing.", log_file)
        return 0

    target_case_path = case_path or config.get("text_case")
    table_name = resolve_case_table_name(target_case_path, data_type)
    context = TestResultContext(
        dut_id=sync_result.dut_id,
        execution_id=sync_result.execution_id,
        case_path=target_case_path,
        data_type=data_type,
        log_file_path=file_path.resolve().as_posix(),
        run_source=run_source,
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
    run_source: str = "FRAMEWORK",
) -> int:
    """High-level helper for syncing a log file to the database."""

    resolved_config = config
    if resolved_config is None:
        try:
            from src.tools.config_loader import load_config  # delayed import
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
        run_source=run_source,
    )
