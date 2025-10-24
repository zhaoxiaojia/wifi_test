from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

import pymysql
import yaml
from pymysql.cursors import DictCursor

from src.tools.mysql_tool.schema import ensure_report_tables


def _config_path_candidates() -> list[Path]:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "config" / "tool_config.yaml")
        mei_dir = getattr(sys, "_MEIPASS", None)
        if mei_dir:
            candidates.append(Path(mei_dir) / "config" / "tool_config.yaml")
    repo_root = Path(__file__).resolve().parents[2]
    candidates.append(repo_root / "config" / "tool_config.yaml")
    candidates.append(Path.cwd() / "config" / "tool_config.yaml")

    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            unique_candidates.append(path)
            seen.add(key)
    return unique_candidates


def load_mysql_settings() -> Dict[str, Any]:
    candidates = _config_path_candidates()
    config_path = next((path for path in candidates if path.is_file()), None)
    if not config_path:
        logging.error("MySQL config file not found. searched=%s", " | ".join(str(path) for path in candidates))
        return {}
    try:
        with config_path.open(encoding="utf-8") as fh:
            payload = yaml.safe_load(fh) or {}
    except Exception as exc:
        logging.error("Failed to read %s: %s", config_path, exc)
        return {}
    logging.debug("Loaded MySQL settings from %s", config_path)
    mysql_cfg = payload.get("mysql") or {}
    settings = {
        "host": mysql_cfg.get("host"),
        "port": int(mysql_cfg.get("port", 3306)) if mysql_cfg.get("port") else 3306,
        "user": str(mysql_cfg.get("user")) if mysql_cfg.get("user") is not None else None,
        "password": str(mysql_cfg.get("passwd")) if mysql_cfg.get("passwd") is not None else None,
        "database": mysql_cfg.get("database"),
        "charset": mysql_cfg.get("charset", "utf8mb4"),
    }
    missing = [key for key in ("host", "user", "password", "database") if not settings.get(key)]
    if missing:
        logging.error("MySQL settings missing keys: %s", ", ".join(missing))
        return {}
    return settings


def ensure_database_exists(settings: Dict[str, Any]) -> None:
    db_name = settings.get("database")
    if not db_name:
        raise RuntimeError("Database name missing in MySQL settings")
    connection = pymysql.connect(
        host=settings.get("host"),
        port=settings.get("port", 3306),
        user=settings.get("user"),
        password=settings.get("password"),
        charset=settings.get("charset", "utf8mb4"),
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()


@dataclass
class ConfigSyncResult:
    dut_id: int
    execution_id: int


def derive_case_root(case_path: str) -> str:
    if not case_path:
        return "default_case"
    try:
        parts = Path(case_path).parts
        if "test" in parts:
            idx = parts.index("test")
            if idx + 1 < len(parts):
                candidate = parts[idx + 1]
            else:
                candidate = parts[-1]
        else:
            candidate = parts[0]
    except Exception:
        candidate = case_path
    sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", candidate).strip("_")
    return sanitized.lower() or "default_case"


class _ConnectionAdapter:
    def __init__(self, connection: pymysql.connections.Connection) -> None:
        self._connection = connection

    def execute(self, sql: str, params: Tuple[Any, ...] | Dict[str, Any] | None = None) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
        self._connection.commit()

    def query_all(self, sql: str, params: Tuple[Any, ...] | Dict[str, Any] | None = None):
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        return list(rows)


class ConfigDatabaseSync:

    def __init__(self) -> None:
        self.settings = load_mysql_settings()
        if not self.settings:
            raise RuntimeError("MySQL settings unavailable")
        ensure_database_exists(self.settings)
        self.connection = pymysql.connect(
            host=self.settings.get("host"),
            port=self.settings.get("port", 3306),
            user=self.settings.get("user"),
            password=self.settings.get("password"),
            charset=self.settings.get("charset", "utf8mb4"),
            database=self.settings.get("database"),
            autocommit=False,
            cursorclass=DictCursor,
        )
        self.ensure_tables()

    def close(self) -> None:
        if self.connection:
            self.connection.close()

    def __enter__(self) -> "ConfigDatabaseSync":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc:
            self.connection.rollback()
        self.close()

    def ensure_tables(self) -> None:
        adapter = _ConnectionAdapter(self.connection)
        logging.debug("Ensuring reporting tables exist in %s", self.settings.get("database"))
        ensure_report_tables(adapter)

    @staticmethod
    def _build_null_safe_conditions(columns: Sequence[str]) -> str:
        segments = []
        for column in columns:
            segments.append(f"((`{column}` IS NULL AND %s IS NULL) OR (`{column}` = %s))")
        return " AND ".join(segments)

    def _find_existing_row_id(
        self,
        cursor,
        table: str,
        columns: Sequence[str],
        values: Sequence[Any],
    ) -> int | None:
        if not columns:
            return None
        conditions = self._build_null_safe_conditions(columns)
        params: list[Any] = []
        for value in values:
            params.extend([value, value])
        sql = f"SELECT id FROM `{table}` WHERE {conditions} ORDER BY id DESC LIMIT 1"
        cursor.execute(sql, params)
        row = cursor.fetchone()
        if not row:
            return None
        return row.get("id")

    def sync_config(self, dut_payload: Dict[str, Any], execution_payload: Dict[str, Any]) -> ConfigSyncResult:
        self.ensure_tables()
        logging.debug("Syncing configuration to DB | dut=%s | execution=%s", dut_payload, execution_payload)
        try:
            with self.connection.cursor() as cursor:
                dut_columns = [
                    "software_version",
                    "driver_version",
                    "hardware_version",
                    "android_version",
                    "kernel_version",
                    "connect_type",
                    "adb_device",
                    "telnet_ip",
                    "product_line",
                    "project",
                    "main_chip",
                    "wifi_module",
                    "interface",
                ]
                dut_values = [
                    dut_payload.get("software_version"),
                    dut_payload.get("driver_version"),
                    dut_payload.get("hardware_version"),
                    dut_payload.get("android_version"),
                    dut_payload.get("kernel_version"),
                    dut_payload.get("connect_type"),
                    dut_payload.get("adb_device"),
                    dut_payload.get("telnet_ip"),
                    dut_payload.get("product_line"),
                    dut_payload.get("project"),
                    dut_payload.get("main_chip"),
                    dut_payload.get("wifi_module"),
                    dut_payload.get("interface"),
                ]
                existing_dut_id = self._find_existing_row_id(cursor, "dut", dut_columns, dut_values)
                if existing_dut_id is not None:
                    dut_id = existing_dut_id
                    logging.info("Reused existing DUT row id=%s", dut_id)
                else:
                    cursor.execute(
                        f"INSERT INTO dut ({', '.join(f'`{column}`' for column in dut_columns)}) "
                        f"VALUES ({', '.join(['%s'] * len(dut_columns))})",
                        dut_values,
                    )
                    dut_id = cursor.lastrowid
                    logging.info("Inserted DUT row id=%s", dut_id)

                case_path = execution_payload.get("case_path")
                case_root = execution_payload.get("case_root") or derive_case_root(case_path or "")
                execution_columns = [
                    "case_path",
                    "case_root",
                    "router_name",
                    "router_address",
                    "rf_model",
                    "corner_model",
                    "lab_name",
                ]
                execution_values = [
                    case_path,
                    case_root,
                    execution_payload.get("router_name"),
                    execution_payload.get("router_address"),
                    execution_payload.get("rf_model"),
                    execution_payload.get("corner_model"),
                    execution_payload.get("lab_name"),
                ]
                logging.debug("Prepared execution values: %s", execution_values)

                existing_execution_id = self._find_existing_row_id(
                    cursor, "execution", execution_columns, execution_values
                )
                if existing_execution_id is not None:
                    execution_id = existing_execution_id
                    logging.info("Reused existing execution row id=%s", execution_id)
                else:
                    cursor.execute(
                        f"INSERT INTO execution ({', '.join(f'`{column}`' for column in execution_columns)}) "
                        f"VALUES ({', '.join(['%s'] * len(execution_columns))})",
                        execution_values,
                    )
                    execution_id = cursor.lastrowid
                    logging.info("Inserted execution row id=%s", execution_id)
            self.connection.commit()
            return ConfigSyncResult(dut_id=dut_id, execution_id=execution_id)
        except Exception:
            logging.exception("Failed to sync configuration to database")
            self.connection.rollback()
            raise

    def fetch_latest_execution_id(self) -> int | None:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT id FROM execution ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
        if not row:
            logging.debug("No execution rows found when fetching latest id.")
            return None
        return row["id"]


__all__ = ["ConfigDatabaseSync", "ConfigSyncResult", "derive_case_root", "load_mysql_settings"]
