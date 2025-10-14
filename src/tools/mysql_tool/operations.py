from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .client import MySqlClient
from .schema import read_csv_rows

__all__ = [
    "PerformanceTableManager",
    "sync_configuration",
    "sync_test_result_to_db",
    "sync_file_to_db",
]


class PerformanceTableManager:
    """Manage the `performance` table that mirrors the latest CSV content."""

    TABLE_NAME = "performance"

    def __init__(self, client: MySqlClient) -> None:
        self._client = client
        self._ensure_table()

    def _ensure_table(self) -> None:
        create_sql = (
            "CREATE TABLE IF NOT EXISTS `performance` ("
            "    `id` INT PRIMARY KEY AUTO_INCREMENT,"
            "    `csv_name` VARCHAR(255) NOT NULL,"
            "    `row_index` INT NOT NULL,"
            "    `data_type` VARCHAR(64) NULL DEFAULT NULL,"
            "    `run_source` VARCHAR(32) NULL DEFAULT NULL,"
            "    `payload` JSON NOT NULL,"
            "    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
        )
        self._client.execute(create_sql)

    @staticmethod
    def _normalize_row(row: Dict[str, Any], headers: Sequence[str]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for header in headers:
            if not header:
                continue
            value = row.get(header)
            if isinstance(value, str):
                normalized[header] = value.strip()
            else:
                normalized[header] = value
        return normalized

    def replace_with_csv(
        self,
        *,
        csv_name: str,
        headers: Sequence[str],
        rows: Sequence[Dict[str, Any]],
        data_type: Optional[str],
        run_source: str,
    ) -> int:
        """Replace table contents with rows parsed from the current CSV file."""

        logging.debug(
            "Preparing to replace %s table contents with data from %s", self.TABLE_NAME, csv_name
        )
        self._client.execute(f"TRUNCATE TABLE `{self.TABLE_NAME}`")

        if not rows:
            logging.info("CSV %s contains no rows; %s table cleared.", csv_name, self.TABLE_NAME)
            return 0

        insert_sql = (
            "INSERT INTO `performance` ("
            "`csv_name`, `row_index`, `data_type`, `run_source`, `payload`) "
            "VALUES (%s, %s, %s, %s, %s)"
        )

        values: List[List[Any]] = []
        for index, row in enumerate(rows, start=1):
            normalized = self._normalize_row(row, headers)
            values.append(
                [
                    csv_name,
                    index,
                    data_type,
                    run_source,
                    json.dumps(normalized, ensure_ascii=False),
                ]
            )

        affected = self._client.executemany(insert_sql, values)
        logging.info(
            "Stored %s rows from %s into %s", affected, csv_name, self.TABLE_NAME
        )
        return affected


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
