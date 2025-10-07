from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pymysql
from pymysql.cursors import DictCursor

from .config import ensure_database_exists, load_mysql_config


class MySqlClient:
    """Thin wrapper around pymysql with helpers for schema operations."""

    def __init__(self, *, autocommit: bool = False):
        self._connection: Optional[pymysql.connections.Connection] = None
        self._config = load_mysql_config()
        if not self._config or not self._config.get("host"):
            raise RuntimeError("Missing MySQL connection parameters.")
        ensure_database_exists(self._config)
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
