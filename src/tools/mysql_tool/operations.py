from __future__ import annotations

import logging
import json
from hashlib import md5
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .client import MySqlClient
from .models import SyncResult, TestResultContext
from .schema import read_csv_rows

_LATEST_SYNC_RESULT: Optional[SyncResult] = None

_TESTER_KEYS = (
    "tester",
    "test_operator",
    "operator",
    "test_engineer",
    "test_user",
)

_CASE_NAME_KEYS = (
    "case_name",
    "test_case_name",
    "testcase_name",
    "testcase",
    "case",
)


def _make_fingerprint(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return md5(serialized.encode("utf-8")).hexdigest()


def _extract_tester(config: Optional[dict]) -> Optional[str]:
    if not isinstance(config, dict):
        return None
    for key in _TESTER_KEYS:
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    metadata = config.get("metadata") if isinstance(config, dict) else None
    if isinstance(metadata, dict):
        for key in _TESTER_KEYS:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _extract_case_name(
    config: Optional[dict], case_path: Optional[str], data_type: Optional[str]
) -> Optional[str]:
    if isinstance(config, dict):
        for key in _CASE_NAME_KEYS:
            value = config.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if case_path:
        return Path(case_path).stem
    if data_type:
        stripped = data_type.strip()
        return stripped.upper() if stripped else None
    return None

__all__ = [
    "ConfigSchemaSynchronizer",
    "TestReportManager",
    "TestResultTableManager",
    "sync_configuration",
    "sync_test_result_to_db",
    "sync_file_to_db",
]


class ConfigSchemaSynchronizer:
    """Persist DUT / Execution 配置信息并避免重复写入。"""

    DUT_TABLE = "dut_settings"
    EXECUTION_TABLE = "execution_settings"

    def __init__(self, client: MySqlClient) -> None:
        self._client = client

    def sync(self, config: dict) -> SyncResult:
        from src.tools.config_sections import split_config_data  # local import to avoid cycle

        dut_section, execution_section = split_config_data(config)
        dut_id = self._ensure_dut_record(dut_section)
        execution_id = self._ensure_execution_record(execution_section, dut_id)
        return SyncResult(dut_id=dut_id, execution_id=execution_id)

    def _ensure_dut_record(self, payload: Optional[dict]) -> int:
        self._ensure_table(self.DUT_TABLE)
        normalized = payload or {}
        fingerprint = _make_fingerprint(normalized)
        row = self._client.query_one(
            f"SELECT id FROM `{self.DUT_TABLE}` WHERE fingerprint=%s",
            [fingerprint],
        )
        if row:
            return int(row["id"])
        logging.debug("Insert new DUT settings with fingerprint %s", fingerprint)
        payload_json = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
        sql = (
            f"INSERT INTO `{self.DUT_TABLE}` (fingerprint, payload) "
            "VALUES (%s, %s)"
        )
        return self._client.insert(sql, [fingerprint, payload_json])

    def _ensure_execution_record(self, payload: Optional[dict], dut_id: int) -> int:
        self._ensure_table(self.EXECUTION_TABLE, include_dut=True)
        normalized = payload or {}
        fingerprint = _make_fingerprint({"dut_id": dut_id, "payload": normalized})
        row = self._client.query_one(
            f"SELECT id FROM `{self.EXECUTION_TABLE}` WHERE fingerprint=%s",
            [fingerprint],
        )
        if row:
            return int(row["id"])
        logging.debug(
            "Insert new execution settings with fingerprint %s (dut_id=%s)",
            fingerprint,
            dut_id,
        )
        payload_json = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
        sql = (
            f"INSERT INTO `{self.EXECUTION_TABLE}` (dut_id, fingerprint, payload) "
            "VALUES (%s, %s, %s)"
        )
        return self._client.insert(sql, [dut_id, fingerprint, payload_json])

    def _ensure_table(self, table_name: str, *, include_dut: bool = False) -> None:
        parts = [
            f"CREATE TABLE IF NOT EXISTS `{table_name}` (",
            "    `id` INT PRIMARY KEY AUTO_INCREMENT,",
        ]
        if include_dut:
            parts.append("    `dut_id` INT NOT NULL,")
        parts.extend(
            [
                "    `fingerprint` CHAR(32) NOT NULL,",
                "    `payload` JSON NOT NULL,",
                "    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,",
                "    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,",
                "    UNIQUE KEY `uniq_fingerprint` (`fingerprint`)",
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;",
            ]
        )
        create_sql = "\n".join(parts)
        self._client.execute(create_sql)


class TestResultTableManager:
    """将性能 CSV 行写入统一的 performance 表。"""

    TABLE_NAME = "performance"

    def __init__(self, client: MySqlClient) -> None:
        self._client = client
        self._ensure_table()

    def _ensure_table(self) -> None:
        create_sql = (
            "CREATE TABLE IF NOT EXISTS `performance` ("
            "    `id` INT PRIMARY KEY AUTO_INCREMENT,"
            "    `test_report_id` INT NOT NULL,"
            "    `row_index` INT NOT NULL,"
            "    `data_type` VARCHAR(64) NULL DEFAULT NULL,"
            "    `run_source` VARCHAR(32) NOT NULL,"
            "    `metrics` JSON NOT NULL,"
            "    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
        )
        self._client.execute(create_sql)

    def store_results(
        self,
        report_id: int,
        headers: Sequence[str],
        rows: Sequence[Dict[str, Any]],
        context: TestResultContext,
    ) -> int:
        if not rows:
            logging.info(
                "No rows parsed from %s, skip inserting into %s",
                context.log_file_path,
                self.TABLE_NAME,
            )
            return 0

        normalized_headers = [header for header in headers if header]
        sql = (
            "INSERT INTO `performance` ("
            "`test_report_id`, `row_index`, `data_type`, `run_source`, `metrics`) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        values_list: List[List[Any]] = []
        for index, row in enumerate(rows, start=1):
            metrics: Dict[str, Any] = {}
            for header in normalized_headers:
                value = row.get(header)
                if value is None:
                    continue
                if isinstance(value, str):
                    text = value.strip()
                    if not text:
                        continue
                    metrics[header] = text
                else:
                    metrics[header] = value
            values_list.append(
                [
                    report_id,
                    index,
                    context.data_type.upper() if context.data_type else None,
                    context.run_source,
                    json.dumps(metrics, ensure_ascii=False),
                ]
            )

        affected = self._client.executemany(sql, values_list)
        logging.info("Stored %s rows into %s", affected, self.TABLE_NAME)
        return affected


class TestReportManager:
    """Record a summary entry referencing DUT, execution and performance data."""

    TABLE_NAME = "test_report"

    def __init__(self, client: MySqlClient) -> None:
        self._client = client
        self._ensure_table()

    def _ensure_table(self) -> None:
        create_sql = (
            "CREATE TABLE IF NOT EXISTS `test_report` ("
            "    `id` INT PRIMARY KEY AUTO_INCREMENT,"
            "    `tester` VARCHAR(128) NULL DEFAULT NULL,"
            "    `test_case_name` VARCHAR(255) NULL DEFAULT NULL,"
            "    `case_path` TEXT NULL DEFAULT NULL,"
            "    `data_type` VARCHAR(64) NULL DEFAULT NULL,"
            "    `log_file_path` TEXT NULL DEFAULT NULL,"
            "    `run_source` VARCHAR(32) NOT NULL,"
            "    `dut_settings_id` INT NOT NULL,"
            "    `execution_settings_id` INT NOT NULL,"
            "    `performance_rows` INT NOT NULL DEFAULT 0,"
            "    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
        )
        self._client.execute(create_sql)

    def create(
        self,
        *,
        tester: Optional[str],
        test_case_name: Optional[str],
        case_path: Optional[str],
        data_type: Optional[str],
        log_file_path: str,
        run_source: str,
        dut_id: int,
        execution_id: int,
    ) -> int:
        sql = (
            "INSERT INTO `test_report` ("
            "`tester`, `test_case_name`, `case_path`, `data_type`, "
            "`log_file_path`, `run_source`, `dut_settings_id`, `execution_settings_id`) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        )
        return self._client.insert(
            sql,
            [
                tester,
                test_case_name,
                case_path,
                data_type,
                log_file_path,
                run_source,
                dut_id,
                execution_id,
            ],
        )

    def update_row_count(self, report_id: int, rows: int) -> None:
        self._client.execute(
            "UPDATE `test_report` SET `performance_rows`=%s WHERE `id`=%s",
            [rows, report_id],
        )


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
            # 确保测试报告表在首次同步配置时即被创建
            TestReportManager(client)
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
            report_manager = TestReportManager(client)
            tester = _extract_tester(config)
            case_name = _extract_case_name(config, target_case_path, context.data_type)
            report_id = report_manager.create(
                tester=tester,
                test_case_name=case_name,
                case_path=target_case_path,
                data_type=context.data_type.upper() if context.data_type else None,
                log_file_path=context.log_file_path,
                run_source=context.run_source,
                dut_id=context.dut_id,
                execution_id=context.execution_id,
            )
            manager = TestResultTableManager(client)
            affected = manager.store_results(report_id, headers, rows, context)
            report_manager.update_row_count(report_id, affected)
        return affected
    except Exception:
        logging.exception("Failed to sync test results into performance table")
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
