from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

import pymysql
import yaml
from pymysql.cursors import DictCursor
import hashlib

from src.tools.mysql_tool.schema import ensure_report_tables
BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = BASE_DIR / "config" / "tool_config.yaml"


def load_mysql_settings() -> Dict[str, Any]:
    try:
        with CONFIG_PATH.open(encoding="utf-8") as fh:
            payload = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        logging.error("MySQL config file not found: %s", CONFIG_PATH)
        return {}
    except Exception as exc:
        logging.error("Failed to read %s: %s", CONFIG_PATH, exc)
        return {}
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


def _hash_values(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if isinstance(value, bool):
            normalized = "1" if value else "0"
        elif value is None:
            normalized = "<NULL>"
        else:
            normalized = str(value)
        parts.append(normalized)
    payload = "\u001f".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    def _bool(value: Any) -> int:
        return 1 if bool(value) else 0

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
                    "third_party_enabled",
                    "third_party_wait",
                    "fpga_series",
                    "fpga_interface",
                    "serial_port_status",
                    "serial_port_port",
                    "serial_port_baud",
                    "profile_hash",
                ]
                base_dut_values = [
                    dut_payload.get("software_version"),
                    dut_payload.get("driver_version"),
                    dut_payload.get("hardware_version"),
                    dut_payload.get("android_version"),
                    dut_payload.get("kernel_version"),
                    dut_payload.get("connect_type"),
                    dut_payload.get("adb_device"),
                    dut_payload.get("telnet_ip"),
                    self._bool(dut_payload.get("third_party_enabled")),
                    dut_payload.get("third_party_wait"),
                    dut_payload.get("fpga_series"),
                    dut_payload.get("fpga_interface"),
                    self._bool(dut_payload.get("serial_port_status")),
                    dut_payload.get("serial_port_port"),
                    dut_payload.get("serial_port_baud"),
                ]
                dut_hash = _hash_values(*base_dut_values)
                dut_values = base_dut_values + [dut_hash]
                logging.debug("Prepared DUT values: %s | hash=%s", base_dut_values, dut_hash)
                cursor.execute(
                    f"INSERT INTO dut ({', '.join(dut_columns)}) VALUES ({', '.join(['%s'] * len(dut_columns))}) "
                    "ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)",
                    dut_values,
                )
                dut_id = cursor.lastrowid
                if cursor.rowcount == 1:
                    logging.info("Inserted DUT row id=%s", dut_id)
                else:
                    logging.info("Reused existing DUT row id=%s", dut_id)

                case_path = execution_payload.get("case_path")
                case_root = execution_payload.get("case_root") or derive_case_root(case_path or "")
                execution_columns = [
                    "case_path",
                    "case_root",
                    "router_name",
                    "router_address",
                    "csv_path",
                    "profile_hash",
                ]
                base_execution_values = [
                    case_path,
                    case_root,
                    execution_payload.get("router_name"),
                    execution_payload.get("router_address"),
                    execution_payload.get("csv_path"),
                ]
                execution_hash = _hash_values(*base_execution_values)
                execution_values = base_execution_values + [execution_hash]
                logging.debug("Prepared execution values: %s | hash=%s", base_execution_values, execution_hash)
                cursor.execute(
                    f"INSERT INTO execution ({', '.join(execution_columns)}) VALUES ({', '.join(['%s'] * len(execution_columns))}) "
                    "ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)",
                    execution_values,
                )
                execution_id = cursor.lastrowid
                if cursor.rowcount == 1:
                    logging.info("Inserted execution row id=%s", execution_id)
                else:
                    logging.info("Reused existing execution row id=%s", execution_id)
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
