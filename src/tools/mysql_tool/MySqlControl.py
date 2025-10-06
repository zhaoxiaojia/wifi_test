#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/15 15:22
# @Author  : chao.li
# @File    : MySqlControl.py

import csv
import hashlib
import logging
import sys
import yaml
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pymysql
from pymysql.cursors import DictCursor

BASE_DIR = Path(__file__).resolve().parents[3]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATA_TABLE_NAME = "performance_data"
CSV_FIELD_MAP: Tuple[Tuple[str, str], ...] = (
    ("SerianNumber", "serial_number"),
    ("Test_Category", "test_category"),
    ("Sub_Category", "sub_category"),
    ("Coex_Method", "coex_method"),
    ("BT_WF_Isolation", "bt_wf_isolation"),
    ("Standard", "standard"),
    ("Freq_Band", "freq_band"),
    ("BW", "bw"),
    ("Data_Rate", "data_rate"),
    ("CH_Freq_MHz", "ch_freq_mhz"),
    ("Protocol", "protocol"),
    ("Direction", "direction"),
    ("Total_Path_Loss", "total_path_loss"),
    ("RxP", "rxp"),
    ("DB", "db_value"),
    ("RSSI", "rssi"),
    ("Angel", "angle"),
    ("Data_RSSI", "data_rssi"),
    ("MCS_Rate", "mcs_rate"),
    ("Throughput", "throughput"),
    ("Expect_Rate", "expect_rate"),
)
TABLE_COLUMN_SQL: Tuple[Tuple[str, str], ...] = (
    ("execution_id", "INT"),
    ("data_type", "VARCHAR(32) NOT NULL"),
    ("file_name", "VARCHAR(255) NOT NULL"),
    ("serial_number", "VARCHAR(128)"),
    ("test_category", "VARCHAR(128)"),
    ("sub_category", "VARCHAR(128)"),
    ("coex_method", "VARCHAR(128)"),
    ("bt_wf_isolation", "VARCHAR(128)"),
    ("standard", "VARCHAR(64)"),
    ("freq_band", "VARCHAR(64)"),
    ("bw", "VARCHAR(64)"),
    ("data_rate", "VARCHAR(64)"),
    ("ch_freq_mhz", "VARCHAR(64)"),
    ("protocol", "VARCHAR(64)"),
    ("direction", "VARCHAR(64)"),
    ("total_path_loss", "VARCHAR(64)"),
    ("rxp", "VARCHAR(64)"),
    ("db_value", "VARCHAR(64)"),
    ("rssi", "VARCHAR(64)"),
    ("angle", "VARCHAR(64)"),
    ("data_rssi", "VARCHAR(64)"),
    ("mcs_rate", "VARCHAR(64)"),
    ("throughput", "VARCHAR(64)"),
    ("expect_rate", "VARCHAR(64)"),
)
TABLE_COLUMN_NAMES: Tuple[str, ...] = tuple(name for name, _ in TABLE_COLUMN_SQL)


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


@dataclass
class DataRecord:
    """Row stored in performance_data table."""

    id: int
    data_type: str
    file_name: str
    serial_number: str
    test_category: str
    sub_category: str
    coex_method: str
    bt_wf_isolation: str
    standard: str
    freq_band: str
    bw: str
    data_rate: str
    ch_freq_mhz: str
    protocol: str
    direction: str
    total_path_loss: str
    rxp: str
    db_value: str
    rssi: str
    angle: str
    data_rssi: str
    mcs_rate: str
    throughput: str
    expect_rate: str
    created_at: datetime
    updated_at: datetime


class MySqlClient:
    """Thin wrapper around pymysql with helpers for CSV storage."""

    def _table_schema_matches(self) -> bool:
        try:
            rows = self.query_all(f"SHOW COLUMNS FROM {DATA_TABLE_NAME}")
        except pymysql.err.ProgrammingError:
            return False
        expected = ["id"] + list(TABLE_COLUMN_NAMES) + ["created_at", "updated_at"]
        actual = [row["Field"] for row in rows]
        return actual == expected

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

    def ensure_data_table(self) -> None:
        column_sql = ",\n            ".join(f"{name} {definition}" for name, definition in TABLE_COLUMN_SQL)
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {DATA_TABLE_NAME} (
            id INT PRIMARY KEY AUTO_INCREMENT,
            {column_sql},
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_data_type_file (data_type, file_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        self.execute(create_sql)

    def drop_data_table(self) -> None:
        self.execute(f"DROP TABLE IF EXISTS {DATA_TABLE_NAME}")

    def import_csv(self, data_type: str, file_path: str, *, overwrite: bool = True) -> int:
        target = Path(file_path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        with target.open(encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError("CSV file has no header row.")
            rows: List[List[str]] = []
            for row in reader:
                values = [str(row.get(csv_key, "")).strip() for csv_key, _ in CSV_FIELD_MAP]
                rows.append(values)
        if not rows:
            logging.warning("CSV file %s does not contain any data rows.", target)
            return 0
        column_names = ",".join(name for _, name in CSV_FIELD_MAP)
        placeholders = ",".join(["%s"] * (len(CSV_FIELD_MAP) + 2))
        insert_sql = (
            f"INSERT INTO {DATA_TABLE_NAME} (data_type, file_name, {column_names}) "
            f"VALUES ({placeholders})"
        )
        params = [[data_type.upper(), target.name, *values] for values in rows]
        with self._connection.cursor() as cursor:
            if overwrite:
                cursor.execute(
                    f"DELETE FROM {DATA_TABLE_NAME} WHERE data_type=%s AND file_name=%s",
                    (data_type.upper(), target.name),
                )
            cursor.executemany(insert_sql, params)
        self.commit()
        logging.info(
            "Stored %s rows from %s into %s", len(rows), target.name, DATA_TABLE_NAME
        )
        return len(rows)

    def delete_record(self, record_id: int) -> int:
        affected = self.execute(f"DELETE FROM {DATA_TABLE_NAME} WHERE id=%s", (record_id,))
        logging.info("Deleted record %s (rows affected: %s)", record_id, affected)
        return affected

    def list_records(
        self,
        *,
        data_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[DataRecord]:
        select_columns = TABLE_COLUMN_NAMES
        sql = (
            f"SELECT id, {', '.join(select_columns)}, created_at, updated_at FROM {DATA_TABLE_NAME}"
        )
        params: List[Any] = []
        if data_type:
            sql += " WHERE data_type=%s"
            params.append(data_type.upper())
        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        rows = self.query_all(sql, params)
        return [
            DataRecord(
                id=row["id"],
                data_type=row["data_type"],
                file_name=row["file_name"],
                serial_number=row["serial_number"],
                test_category=row["test_category"],
                sub_category=row["sub_category"],
                coex_method=row["coex_method"],
                bt_wf_isolation=row["bt_wf_isolation"],
                standard=row["standard"],
                freq_band=row["freq_band"],
                bw=row["bw"],
                data_rate=row["data_rate"],
                ch_freq_mhz=row["ch_freq_mhz"],
                protocol=row["protocol"],
                direction=row["direction"],
                total_path_loss=row["total_path_loss"],
                rxp=row["rxp"],
                db_value=row["db_value"],
                rssi=row["rssi"],
                angle=row["angle"],
                data_rssi=row["data_rssi"],
                mcs_rate=row["mcs_rate"],
                throughput=row["throughput"],
                expect_rate=row["expect_rate"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def get_record(self, record_id: int) -> Optional[DataRecord]:
        select_columns = TABLE_COLUMN_NAMES
        sql = (
            f"SELECT id, {', '.join(select_columns)}, created_at, updated_at FROM {DATA_TABLE_NAME} "
            "WHERE id=%s"
        )
        row = self.query_one(sql, (record_id,))
        if not row:
            return None
        return DataRecord(
            id=row["id"],
            data_type=row["data_type"],
            file_name=row["file_name"],
            serial_number=row["serial_number"],
            test_category=row["test_category"],
            sub_category=row["sub_category"],
            coex_method=row["coex_method"],
            bt_wf_isolation=row["bt_wf_isolation"],
            standard=row["standard"],
            freq_band=row["freq_band"],
            bw=row["bw"],
            data_rate=row["data_rate"],
            ch_freq_mhz=row["ch_freq_mhz"],
            protocol=row["protocol"],
            direction=row["direction"],
            total_path_loss=row["total_path_loss"],
            rxp=row["rxp"],
            db_value=row["db_value"],
            rssi=row["rssi"],
            angle=row["angle"],
            data_rssi=row["data_rssi"],
            mcs_rate=row["mcs_rate"],
            throughput=row["throughput"],
            expect_rate=row["expect_rate"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def __del__(self):  # pragma: no cover
        try:
            self.close()
        except Exception:
            pass


def sync_file_to_db(
    file_path: str,
    data_type: str,
    *,
    overwrite: bool = True,
) -> int:
    client = MySqlClient()
    try:
        client.ensure_data_table()
        row_count = client.import_csv(data_type, file_path, overwrite=overwrite)
        return row_count
    except Exception as exc:
        logging.error("Failed to sync CSV file to database: %s", exc)
        return 0
    finally:
        client.close()


__all__ = ["MySqlClient", "DataRecord", "sync_file_to_db"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        with MySqlClient() as client:
            client.ensure_data_table()
            records = client.list_records(limit=5)
            if not records:
                logging.info("No records found in %s, inserting a sample row for local verification", DATA_TABLE_NAME)
                sample_path = BASE_DIR / "sample_performance.csv"
                with sample_path.open("w", newline="", encoding="utf-8") as sample_file:
                    writer = csv.writer(sample_file)
                    writer.writerow([csv_key for csv_key, _ in CSV_FIELD_MAP])
                    writer.writerow([
                        "SN0001",
                        "RVR",
                        "SubCase",
                        "Standalone",
                        "Null",
                        "11AX",
                        "5G",
                        "80",
                        "HE-160",
                        "149",
                        "TCP",
                        "UL",
                        "30",
                        "-45",
                        "-3",
                        "-40",
                        "15",
                        "-55",
                        "MCS9",
                        "820",
                        "780",
                    ])
                client.import_csv("SAMPLE", str(sample_path), overwrite=True)
                sample_path.unlink(missing_ok=True)
                records = client.list_records(limit=5)
            for record in records:
                logging.info(
                    "Record %s | Type %s | File %s | Serial %s | Throughput %s",
                    record.id,
                    record.data_type,
                    record.file_name,
                    record.serial_number,
                    record.throughput,
                )
    except RuntimeError as exc:
        logging.error("MySQL client initialization failed: %s", exc)
