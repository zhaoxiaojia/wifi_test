from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pymysql
from pymysql.cursors import DictCursor

from .config import ensure_database_exists, load_mysql_config


class MySqlClient:
    """
    My SQL client.

    Establishes and manages a connection to a MySQL database.

    Parameters
    ----------
    None
        This class does not take constructor arguments beyond ``self``.

    Returns
    -------
    None
        This class does not return a value.
    """

    def __init__(self, *, autocommit: bool = False):
        """
        Init.

        Loads configuration settings from a YAML or configuration file.
        Creates the database if it does not already exist.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        None
            This method does not return a value.
        """
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
        """
        Connection.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        Any
            The result produced by the function.
        """
        return self._connection

    def execute(self, sql: str, args: Optional[Sequence[Any]] = None) -> int:
        """
        Execute.

        Runs an SQL statement using a database cursor.
        Commits the current transaction when autocommit is disabled.
        Rolls back the current transaction on error when autocommit is disabled.
        Logs informational messages and errors for debugging purposes.

        Parameters
        ----------
        sql : Any
            SQL statement to execute.
        args : Any
            Sequence of positional arguments for the SQL statement.

        Returns
        -------
        int
            A value of type ``int``.
        """
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
        """
        Executemany.

        Runs an SQL statement using a database cursor.
        Executes multiple SQL statements in a batch using a cursor.
        Commits the current transaction when autocommit is disabled.
        Rolls back the current transaction on error when autocommit is disabled.
        Logs informational messages and errors for debugging purposes.

        Parameters
        ----------
        sql : Any
            SQL statement to execute.
        args_list : Any
            Iterable of parameter sequences for batch execution.

        Returns
        -------
        int
            A value of type ``int``.
        """
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
        """
        Insert.

        Runs an SQL statement using a database cursor.
        Commits the current transaction when autocommit is disabled.
        Rolls back the current transaction on error when autocommit is disabled.
        Logs informational messages and errors for debugging purposes.

        Parameters
        ----------
        sql : Any
            SQL statement to execute.
        args : Any
            Sequence of positional arguments for the SQL statement.

        Returns
        -------
        int
            A value of type ``int``.
        """
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
        """
        Query one.

        Runs an SQL statement using a database cursor.
        Fetches a single row from the result set.
        Logs informational messages and errors for debugging purposes.

        Parameters
        ----------
        sql : Any
            SQL statement to execute.
        args : Any
            Sequence of positional arguments for the SQL statement.

        Returns
        -------
        Optional[Dict[str, Any]]
            A value of type ``Optional[Dict[str, Any]]``.
        """
        logging.debug("Query one SQL: %s | args: %s", sql, args)
        with self._connection.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchone()

    def query_all(self, sql: str, args: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        """
        Query all.

        Runs an SQL statement using a database cursor.
        Fetches all rows from the result set.
        Logs informational messages and errors for debugging purposes.

        Parameters
        ----------
        sql : Any
            SQL statement to execute.
        args : Any
            Sequence of positional arguments for the SQL statement.

        Returns
        -------
        List[Dict[str, Any]]
            A value of type ``List[Dict[str, Any]]``.
        """
        logging.debug("Query all SQL: %s | args: %s", sql, args)
        with self._connection.cursor() as cursor:
            cursor.execute(sql, args)
            rows = cursor.fetchall()
        return list(rows)

    def commit(self) -> None:
        """
        Commit.

        Commits the current transaction when autocommit is disabled.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        None
            This method does not return a value.
        """
        if self._connection and not self._connection.get_autocommit():
            self._connection.commit()

    def rollback(self) -> None:
        """
        Rollback.

        Commits the current transaction when autocommit is disabled.
        Rolls back the current transaction on error when autocommit is disabled.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        None
            This method does not return a value.
        """
        if self._connection and not self._connection.get_autocommit():
            self._connection.rollback()

    def close(self) -> None:
        """
        Close.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        None
            This method does not return a value.
        """
        conn = getattr(self, "_connection", None)
        if conn:
            conn.close()
            self._connection = None

    def __enter__(self) -> "MySqlClient":
        """
        Enter.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        'MySqlClient'
            A value of type ``'MySqlClient'``.
        """
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """
        Exit.

        Rolls back the current transaction on error when autocommit is disabled.

        Parameters
        ----------
        exc_type : Any
            The ``exc_type`` parameter.
        exc : Any
            The ``exc`` parameter.
        tb : Any
            The ``tb`` parameter.

        Returns
        -------
        None
            This method does not return a value.
        """
        if exc:
            self.rollback()
        self.close()

    def __del__(self):  # pragma: no cover
        """
        Del.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        None
            This method does not return a value.
        """
        try:
            self.close()
        except Exception:
            pass
