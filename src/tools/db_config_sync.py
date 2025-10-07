from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

import pymysql
import yaml
from pymysql.cursors import DictCursor

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
        "user": mysql_cfg.get("user"),
        "password": mysql_cfg.get("passwd"),
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


class ConfigDatabaseSync:
    DUT_TABLE_SQL = (
        "id INT PRIMARY KEY AUTO_INCREMENT",
        "software_version VARCHAR(128)",
        "driver_version VARCHAR(128)",
        "hardware_version VARCHAR(128)",
        "android_version VARCHAR(64)",
        "kernel_version VARCHAR(64)",
        "connect_type VARCHAR(32)",
        "adb_device VARCHAR(128)",
        "telnet_ip VARCHAR(128)",
        "third_party_enabled TINYINT(1)",
        "third_party_wait INT",
        "fpga_series VARCHAR(64)",
        "fpga_interface VARCHAR(64)",
        "serial_port_status TINYINT(1)",
        "serial_port_port VARCHAR(64)",
        "serial_port_baud VARCHAR(64)",
        "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    )

    EXECUTION_TABLE_SQL = (
        "id INT PRIMARY KEY AUTO_INCREMENT",
        "dut_info_id INT NOT NULL",
        "case_path VARCHAR(255)",
        "case_root VARCHAR(128)",
        "router_name VARCHAR(128)",
        "router_address VARCHAR(128)",
        "csv_path VARCHAR(255)",
        "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        "INDEX idx_case_root (case_root)",
        "CONSTRAINT fk_execution_dut FOREIGN KEY (dut_info_id) REFERENCES dut_info(id) ON DELETE CASCADE",
    )

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

    def close(self) -> None:
        if self.connection:
            self.connection.close()

    def __enter__(self) -> "ConfigDatabaseSync":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc:
            self.connection.rollback()
        self.close()

    def _execute(self, sql: str, params: Tuple[Any, ...] | Dict[str, Any] | None = None) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)

    def ensure_tables(self) -> None:
        dut_columns = ",\n            ".join(self.DUT_TABLE_SQL)
        exec_columns = ",\n            ".join(self.EXECUTION_TABLE_SQL)
        self._execute(
            f"""
            CREATE TABLE IF NOT EXISTS dut_info (
                {dut_columns}
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )
        self._execute(
            f"""
            CREATE TABLE IF NOT EXISTS execution_info (
                {exec_columns}
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )

    @staticmethod
    def _bool(value: Any) -> int:
        return 1 if bool(value) else 0

    def sync_config(self, dut_payload: Dict[str, Any], execution_payload: Dict[str, Any]) -> ConfigSyncResult:
        self.ensure_tables()
        with self.connection.cursor() as cursor:
            cursor.execute("DELETE FROM execution_info")
            cursor.execute("DELETE FROM dut_info")
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
                self._bool(dut_payload.get("third_party_enabled")),
                dut_payload.get("third_party_wait"),
                dut_payload.get("fpga_series"),
                dut_payload.get("fpga_interface"),
                self._bool(dut_payload.get("serial_port_status")),
                dut_payload.get("serial_port_port"),
                dut_payload.get("serial_port_baud"),
            ]
            cursor.execute(
                f"INSERT INTO dut_info ({', '.join(dut_columns)}) VALUES ({', '.join(['%s'] * len(dut_columns))})",
                dut_values,
            )
            dut_id = cursor.lastrowid
            execution_columns = [
                "dut_info_id",
                "case_path",
                "case_root",
                "router_name",
                "router_address",
                "csv_path",
            ]
            execution_values = [
                dut_id,
                execution_payload.get("case_path"),
                execution_payload.get("case_root"),
                execution_payload.get("router_name"),
                execution_payload.get("router_address"),
                execution_payload.get("csv_path"),
            ]
            cursor.execute(
                f"INSERT INTO execution_info ({', '.join(execution_columns)}) VALUES ({', '.join(['%s'] * len(execution_columns))})",
                execution_values,
            )
            execution_id = cursor.lastrowid
        self.connection.commit()
        return ConfigSyncResult(dut_id=dut_id, execution_id=execution_id)

    def fetch_latest_execution_id(self) -> int | None:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT id FROM execution_info ORDER BY updated_at DESC LIMIT 1")
            row = cursor.fetchone()
        return row["id"] if row else None


__all__ = ["ConfigDatabaseSync", "ConfigSyncResult", "derive_case_root", "load_mysql_settings"]
