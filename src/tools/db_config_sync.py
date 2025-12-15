"""Database configuration synchronization utilities.

This module provides helper functions and classes to load MySQL settings
from configuration, ensure that required databases and tables exist, and
synchronize configuration payloads into a MySQL database.  It defines a
dataclass :class:`ConfigSyncResult` for returning identifiers of DUT and
execution rows, and a :class:`ConfigDatabaseSync` class that encapsulates
database connection management and synchronization logic.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

import pymysql
from pymysql.cursors import DictCursor

from src.util.constants import load_config
from src.util.constants import TOOL_CONFIG_FILENAME, TOOL_SECTION_KEY, get_config_base
from src.tools.mysql_tool.schema import ensure_report_tables


def load_mysql_settings() -> Dict[str, Any]:
    """Load MySQL connection settings from the tool configuration.

    This function reads configuration using :func:`load_config` and extracts the
    MySQL connection settings from the tool section.  It validates the presence
    of required keys and returns a dictionary suitable for passing to
    :func:`pymysql.connect`.

    Returns:
        Dict[str, Any]: A dictionary with keys ``host``, ``port``, ``user``,
        ``password``, ``database`` and ``charset``.  An empty dictionary is
        returned and errors are logged if any required settings are missing.
    """
    try:
        config = load_config(refresh=True)
    except Exception as exc:
        logging.error("Failed to load configuration for MySQL: %s", exc)
        return {}
    try:
        tool_cfg = config.get(TOOL_SECTION_KEY) or {}
    except Exception as exc:
        logging.error("Invalid tool section in configuration: %s", exc)
        return {}
    mysql_cfg = tool_cfg.get("mysql") or {}
    config_path = get_config_base() / TOOL_CONFIG_FILENAME
    if not mysql_cfg:
        logging.error("MySQL settings missing mysql section in %s", config_path)
        return {}
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
        logging.error("MySQL settings missing keys in %s: %s", config_path, ", ".join(missing))
        return {}
    return settings


def ensure_database_exists(settings: Dict[str, Any]) -> None:
    """Ensure the target MySQL database exists.

    This helper connects to the MySQL server using the provided connection
    settings and issues a ``CREATE DATABASE IF NOT EXISTS`` statement for
    the ``database`` name found in the settings.  If the ``database`` key is
    missing in the settings, a :class:`RuntimeError` is raised.  The
    connection is automatically closed regardless of whether the database
    creation succeeds.

    Parameters:
        settings (Dict[str, Any]): A dictionary containing at least the
            connection parameters ``host``, ``port``, ``user``, ``password``,
            and ``database``.  Other keys such as ``charset`` are optional.

    Raises:
        RuntimeError: If the ``database`` entry is missing from the
            ``settings`` dictionary.
    """
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
    """Result of a configuration synchronization.

    Instances of this data class are returned from
    :meth:`ConfigDatabaseSync.sync_config`.  They record the primary keys
    of the ``dut`` and ``shielded`` rows that were either created or
    reused during a synchronization operation.

    Parameters:
        dut_id (int): The identifier of the corresponding row in the
            ``dut`` table.
        shielded_id (int): The identifier of the row in the ``shielded``
            table that stores information about a specific test execution.
    """
    dut_id: int
    shielded_id: int


def derive_case_root(case_path: str) -> str:
    """Derive a normalized case root name from a case file path.

    The case root is determined by inspecting the path segments of
    ``case_path``.  If the segment ``"test"`` exists, the following segment
    is chosen as the root.  Otherwise the first segment is used.  The
    resulting string is sanitized to contain only alphanumeric characters
    and underscores and is converted to lower-case.  If ``case_path`` is
    empty or all characters are removed during sanitization, ``"default_case"``
    is returned.

    Parameters:
        case_path (str): The absolute or relative file path of a test case.

    Returns:
        str: A normalized and sanitized case root identifier.
    """
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
    """Lightweight adapter around a PyMySQL connection.

    This helper wraps a :class:`pymysql.connections.Connection` to provide
    simple ``execute`` and ``query_all`` operations with automatic commit
    semantics.  It is used by :func:`ensure_report_tables` to perform
    schema setup without exposing the full database connection and cursor
    management details.

    Parameters:
        connection (pymysql.connections.Connection): An active PyMySQL
            connection.  The adapter does not take ownership of the
            connection's lifecycle; the caller is responsible for closing it.
    """

    def __init__(self, connection: pymysql.connections.Connection) -> None:
        """Initialize the connection adapter.

        Parameters:
            connection (pymysql.connections.Connection): The open connection
                to wrap for executing SQL statements.
        """
        self._connection = connection

    def execute(
        self, sql: str, params: Tuple[Any, ...] | Dict[str, Any] | None = None
    ) -> None:
        """Execute a non-select SQL statement and commit the transaction.

        Parameters:
            sql (str): The SQL statement to execute.  Typically an INSERT,
                UPDATE, DELETE or DDL statement.
            params (Tuple[Any, ...] | Dict[str, Any] | None, optional): A
                sequence or mapping of values to bind to the SQL statement.
                Defaults to ``None`` if no bind parameters are needed.

        Notes:
            The underlying connection's autocommit must be disabled for
            explicit commit semantics to take effect.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
        self._connection.commit()

    def query_all(
        self, sql: str, params: Tuple[Any, ...] | Dict[str, Any] | None = None
    ) -> list[Dict[str, Any]]:
        """Execute a SELECT statement and return all rows.

        Parameters:
            sql (str): The SELECT statement to execute.
            params (Tuple[Any, ...] | Dict[str, Any] | None, optional): Values
                to bind to the SQL statement.  Defaults to ``None``.

        Returns:
            list[Dict[str, Any]]: A list of rows, each represented as a
                dictionary mapping column names to values.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        return list(rows)


class ConfigDatabaseSync:
    """Synchronize configuration payloads into a MySQL database.

    This class encapsulates the logic required to connect to a MySQL database,
    ensure that required reporting tables exist, and insert or reuse rows
    representing device-under-test (DUT) information and execution metadata.
    Instances may be used as context managers to guarantee that the
    underlying connection is properly closed and transactions are committed or
    rolled back.

    Examples:
        >>> sync = ConfigDatabaseSync()
        >>> result = sync.sync_config(dut_payload, execution_payload)
        >>> print(result.dut_id, result.shielded_id)
        >>> sync.close()
    """

    def __init__(self) -> None:
        """Initialize the synchronizer and connect to the database.

        The constructor loads MySQL settings via :func:`load_mysql_settings`,
        ensures the target database exists by calling
        :func:`ensure_database_exists`, opens a PyMySQL connection, and
        invokes :meth:`ensure_tables` to create required tables if they do
        not already exist.

        Raises:
            RuntimeError: If the MySQL settings could not be loaded or are
                incomplete.
        """
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
        """Close the underlying database connection."""
        if self.connection:
            self.connection.close()

    def __enter__(self) -> "ConfigDatabaseSync":
        """Enter the context manager and return ``self``."""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Exit the context manager.

        On exit, if an exception occurred inside the context block, the
        transaction is rolled back; otherwise any pending changes are
        committed.  The database connection is closed in all cases.

        Parameters:
            exc_type: The exception type, if an exception was raised.
            exc: The exception instance, if any.
            tb: The traceback object, if any.
        """
        if exc:
            self.connection.rollback()
        self.close()

    def ensure_tables(self) -> None:
        """Ensure that required reporting tables exist.

        This method delegates to :func:`ensure_report_tables`, passing in
        a :class:`_ConnectionAdapter` for executing the necessary
        ``CREATE TABLE`` statements.  It logs its activity at debug level.
        """
        adapter = _ConnectionAdapter(self.connection)
        logging.debug(
            "Ensuring reporting tables exist in %s", self.settings.get("database")
        )
        ensure_report_tables(adapter)

    @staticmethod
    def _build_null_safe_conditions(columns: Sequence[str]) -> str:
        """Construct SQL predicates for null-safe equality checks.

        Given a sequence of column names, this helper produces a combined
        condition that treats two NULL values as equal.  For each column
        ``c``, the condition takes the form::

            ((`c` IS NULL AND %s IS NULL) OR (`c` = %s))

        The placeholders must be bound twice for each value when executing
        the query.

        Parameters:
            columns (Sequence[str]): The column names to include in the
                comparison.

        Returns:
            str: An SQL predicate string that can be used in a WHERE clause.
        """
        segments = []
        for column in columns:
            segments.append(
                f"((`{column}` IS NULL AND %s IS NULL) OR (`{column}` = %s))"
            )
        return " AND ".join(segments)

    def _find_existing_row_id(
        self,
        cursor,
        table: str,
        columns: Sequence[str],
        values: Sequence[Any],
    ) -> int | None:
        """Find an existing row in the given table matching column values.

        Parameters:
            cursor: A database cursor supporting ``execute`` and ``fetchone``.
            table (str): The table name to search.
            columns (Sequence[str]): Column names that form the match key.
            values (Sequence[Any]): Values corresponding to ``columns``.

        Returns:
            int | None: The ID of the newest matching row or ``None`` if no
                match was found.
        """
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

    def sync_config(
        self, dut_payload: Dict[str, Any], execution_payload: Dict[str, Any]
    ) -> ConfigSyncResult:
        """Synchronize DUT and execution payloads into the database.

        This method inserts or reuses rows in the ``dut`` and ``execution``
        tables based on the provided payload dictionaries.  If a matching row
        exists for a given combination of column values, its ID is reused;
        otherwise a new row is inserted.  Finally the transaction is
        committed and a :class:`ConfigSyncResult` is returned.

        Parameters:
            dut_payload (Dict[str, Any]): A mapping containing attributes of
                the device under test.  Keys correspond to columns in the
                ``dut`` table.
            execution_payload (Dict[str, Any]): A mapping describing
                execution-specific information such as case path and
                instrumentation metadata.  Keys correspond to columns in
                the ``execution`` table.

        Returns:
            ConfigSyncResult: An object holding the IDs of the DUT and
                execution rows that were created or reused.

        Raises:
            Exception: Propagates exceptions from the underlying database
                operations after rolling back the transaction.
        """
        self.ensure_tables()
        logging.debug(
            "Syncing configuration to DB | dut=%s | execution=%s", dut_payload, execution_payload
        )
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
                shielded_columns = [
                    "case_path",
                    "case_root",
                    "router_name",
                    "router_address",
                    "rf_model",
                    "corner_model",
                    "lab_name",
                ]
                shielded_values = [
                    case_path,
                    case_root,
                    execution_payload.get("router_name"),
                    execution_payload.get("router_address"),
                    execution_payload.get("rf_model"),
                    execution_payload.get("corner_model"),
                    execution_payload.get("lab_name"),
                ]
                logging.debug("Prepared shielded values: %s", shielded_values)

                existing_shielded_id = self._find_existing_row_id(
                    cursor, "shielded", shielded_columns, shielded_values
                )
                if existing_shielded_id is not None:
                    shielded_id = existing_shielded_id
                    logging.info("Reused existing shielded row id=%s", shielded_id)
                else:
                    cursor.execute(
                        f"INSERT INTO shielded ({', '.join(f'`{column}`' for column in shielded_columns)}) "
                        f"VALUES ({', '.join(['%s'] * len(shielded_columns))})",
                        shielded_values,
                    )
                    shielded_id = cursor.lastrowid
                    logging.info("Inserted shielded row id=%s", shielded_id)
            self.connection.commit()
            return ConfigSyncResult(dut_id=dut_id, shielded_id=shielded_id)
        except Exception:
            logging.exception("Failed to sync configuration to database")
            self.connection.rollback()
            raise

    def fetch_latest_shielded_id(self) -> int | None:
        """Fetch the ID of the most recently inserted shielded row.

        Returns the identifier of the latest entry in the ``shielded`` table
        ordered by descending ``id``.  If no shielded rows exist, ``None``
        is returned.

        Returns:
            int | None: The ID of the most recent shielded row, or ``None``.
        """
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT id FROM shielded ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
        if not row:
            logging.debug(
                "No shielded rows found when fetching latest id."
            )
            return None
        return row["id"]


__all__ = ["ConfigDatabaseSync", "ConfigSyncResult", "derive_case_root", "load_mysql_settings"]
