from __future__ import annotations

import csv
import json
import logging
import re
import textwrap
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, TYPE_CHECKING

from .models import (
    ColumnDefinition,
    HeaderMapping,
    TableConstraint,
    TableIndex,
    TableSpec,
)
from .naming import IdentifierBuilder, sanitize_identifier

if TYPE_CHECKING:  # pragma: no cover
    from .client import MySqlClient

__all__ = [
    "build_section_payload",
    "build_header_mappings",
    "insert_rows",
    "read_csv_rows",
    "resolve_case_table_name",
    "ensure_table",
    "ensure_config_tables",
    "ensure_report_tables",
    "get_table_spec",
    "PERFORMANCE_STATIC_COLUMNS",
]

PERFORMANCE_STATIC_COLUMNS: Tuple[Tuple[str, str, str], ...] = (
    ("serial_number", "VARCHAR(255)", "SerianNumber"),
    ("test_category", "VARCHAR(255)", "Test_Category"),
    (
        "standard",
        "ENUM('11a','11b','11g','11n','11ac','11ax','11be')",
        "Standard",
    ),
    ("band", "ENUM('2.4','5','6')", "Freq_Band"),
    ("bandwidth_mhz", "SMALLINT", "BW"),
    ("phy_rate_mbps", "DECIMAL(10,3)", "Data_Rate"),
    ("center_freq_mhz", "SMALLINT", "CH_Freq_MHz"),
    ("protocol", "VARCHAR(255)", "Protocol"),
    ("direction", "ENUM('uplink','downlink','bi')", "Direction"),
    ("total_path_loss", "DECIMAL(6,2)", "Total_Path_Loss"),
    ("path_loss_db", "DECIMAL(6,2)", "DB"),
    ("rssi", "DECIMAL(6,2)", "RSSI"),
    ("angle_deg", "DECIMAL(6,2)", "Angel"),
    ("mcs_rate", "VARCHAR(255)", "MCS_Rate"),
    ("throughput_peak_mbps", "DECIMAL(10,3)", "Max_Rate"),
    ("throughput_avg_mbps", "DECIMAL(10,3)", "Throughput"),
    ("target_throughput_mbps", "DECIMAL(10,3)", "Expect_Rate"),
    ("latency_ms", "DECIMAL(10,3)", "Latency"),
    ("packet_loss", "VARCHAR(64)", "Packet_Loss"),
    ("profile_mode", "VARCHAR(64)", "Profile_Mode"),
    ("profile_value", "VARCHAR(64)", "Profile_Value"),
    ("scenario_group_key", "VARCHAR(255)", "Scenario_Group_Key"),
)


def _assert_unique_column_names(
        columns: Sequence[Tuple[str, str, str]], *, context: str
) -> None:
    """
    Assert unique column names.

    Parameters
    ----------
    columns : Any
        Sequence of column specifications.

    Returns
    -------
    None
        This function does not return a value.
    """

    seen: set[str] = set()
    duplicates = []
    for name, _, _ in columns:
        if name in seen:
            duplicates.append(name)
        else:
            seen.add(name)
    if duplicates:
        duplicate_list = ", ".join(sorted(set(duplicates)))
        raise ValueError(
            f"Duplicate column name(s) found in {context}: {duplicate_list}"
        )


_assert_unique_column_names(
    PERFORMANCE_STATIC_COLUMNS, context="performance static columns"
)

PERFORMANCE_COLUMN_RENAMES: Tuple[Tuple[str, str], ...] = (
    ("seriannumber", "serial_number"),
    ("serialnumber", "serial_number"),
    ("freq_band", "band"),
    ("freg_band", "band"),
    ("btw", "bandwidth_mhz"),
    ("bw", "bandwidth_mhz"),
    ("data_rate", "phy_rate_mbps"),
    ("ch_freq_mhz", "center_freq_mhz"),
    ("db", "path_loss_db"),
    ("angel", "angle_deg"),
    ("throughput", "throughput_avg_mbps"),
    ("max_rate", "throughput_peak_mbps"),
    ("expect_rate", "target_throughput_mbps"),
)

_AUDIT_COLUMNS: Tuple[ColumnDefinition, ...] = (
    ColumnDefinition("created_at", "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ColumnDefinition(
        "updated_at",
        "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    ),
)

_PERFORMANCE_BASE_COLUMNS: Tuple[ColumnDefinition, ...] = (
    ColumnDefinition("test_report_id", "INT NOT NULL"),
    ColumnDefinition("csv_name", "VARCHAR(255) NOT NULL"),
    ColumnDefinition("data_type", "VARCHAR(64)"),
)


def _build_performance_definition(definition: str, comment: str) -> str:
    """
    Build performance definition.

    Parameters
    ----------
    definition : Any
        Column definition string from the table specification.
    comment : Any
        The ``comment`` parameter.

    Returns
    -------
    str
        A value of type ``str``.
    """
    escaped = comment.replace("'", "''")
    return f"{definition} NULL DEFAULT NULL COMMENT '{escaped}'"


_PERFORMANCE_EXTRA_COLUMNS: Tuple[ColumnDefinition, ...] = tuple(
    ColumnDefinition(name, _build_performance_definition(definition, comment))
    for name, definition, comment in PERFORMANCE_STATIC_COLUMNS
)

_TABLE_SPECS: Dict[str, TableSpec] = {
    "dut": TableSpec(
        columns=(
            ColumnDefinition("software_version", "VARCHAR(128)"),
            ColumnDefinition("driver_version", "VARCHAR(128)"),
            ColumnDefinition("hardware_version", "VARCHAR(128)"),
            ColumnDefinition("android_version", "VARCHAR(64)"),
            ColumnDefinition("kernel_version", "VARCHAR(64)"),
            ColumnDefinition("connect_type", "VARCHAR(64)"),
            ColumnDefinition("adb_device", "VARCHAR(128)"),
            ColumnDefinition("telnet_ip", "VARCHAR(128)"),
            ColumnDefinition("product_line", "VARCHAR(64)"),
            ColumnDefinition("project", "VARCHAR(64)"),
            ColumnDefinition("main_chip", "VARCHAR(64)"),
            ColumnDefinition("wifi_module", "VARCHAR(64)"),
            ColumnDefinition("interface", "VARCHAR(64)"),
        ),
        include_audit_columns=False,
    ),
    "shielded": TableSpec(
        columns=(
            ColumnDefinition("case_path", "VARCHAR(512)"),
            ColumnDefinition("case_root", "VARCHAR(128)"),
            ColumnDefinition("router_name", "VARCHAR(128)"),
            ColumnDefinition("router_address", "VARCHAR(128)"),
            ColumnDefinition("rf_model", "VARCHAR(128)"),
            ColumnDefinition("corner_model", "VARCHAR(128)"),
            ColumnDefinition("lab_name", "VARCHAR(128)"),
        ),
        include_audit_columns=False,
    ),
    "test_report": TableSpec(
        columns=(
            ColumnDefinition("shielded_id", "INT NULL DEFAULT NULL"),
            ColumnDefinition("dut_id", "INT NULL DEFAULT NULL"),
            ColumnDefinition("csv_name", "VARCHAR(255) NOT NULL"),
            ColumnDefinition("csv_path", "VARCHAR(512)"),
            ColumnDefinition("data_type", "VARCHAR(64)"),
            ColumnDefinition("case_path", "VARCHAR(512)"),
            ColumnDefinition("duration_seconds", "INT NULL DEFAULT NULL"),
        ),
        indexes=(
            TableIndex(
                "idx_test_report_shielded", "INDEX idx_test_report_shielded (`shielded_id`)"
            ),
            TableIndex(
                "idx_test_report_dut", "INDEX idx_test_report_dut (`dut_id`)"
            ),
            TableIndex(
                "idx_test_report_created_at",
                "INDEX idx_test_report_created_at (`created_at`)",
            ),
        ),
        constraints=(
            TableConstraint(
                "uq_test_report_shielded_csv",
                "CONSTRAINT uq_test_report_shielded_csv UNIQUE (`shielded_id`, `csv_name`)",
            ),
            TableConstraint(
                "fk_test_report_shielded",
                "CONSTRAINT fk_test_report_shielded FOREIGN KEY (`shielded_id`) REFERENCES `shielded`(`id`)",
            ),
            TableConstraint(
                "fk_test_report_dut",
                "CONSTRAINT fk_test_report_dut FOREIGN KEY (`dut_id`) REFERENCES `dut`(`id`)",
            ),
        ),
    ),
    "router": TableSpec(
        columns=(
            ColumnDefinition("ip", "VARCHAR(64) NOT NULL"),
            ColumnDefinition("port", "INT NOT NULL"),
            ColumnDefinition("brand", "VARCHAR(128)"),
            ColumnDefinition("model", "VARCHAR(128)"),
            ColumnDefinition("payload_json", "JSON"),
        ),
        indexes=(
            TableIndex(
                "idx_router_ip_port",
                "INDEX idx_router_ip_port (`ip`, `port`)",
            ),
        ),
        constraints=(
            TableConstraint(
                "uq_router_ip_port",
                "CONSTRAINT uq_router_ip_port UNIQUE (`ip`, `port`)",
            ),
        ),
    ),
    "compatibility": TableSpec(
        columns=(
            ColumnDefinition("test_report_id", "INT NOT NULL"),
            ColumnDefinition("router_id", "INT NULL DEFAULT NULL"),
            ColumnDefinition("pdu_ip", "VARCHAR(64)"),
            ColumnDefinition("pdu_port", "INT"),
            ColumnDefinition("ap_brand", "VARCHAR(255)"),
            ColumnDefinition("band", "VARCHAR(32)"),
            ColumnDefinition("ssid", "VARCHAR(255)"),
            ColumnDefinition("wifi_mode", "VARCHAR(64)"),
            ColumnDefinition("bandwidth", "VARCHAR(64)"),
            ColumnDefinition("security", "VARCHAR(64)"),
            ColumnDefinition("scan_result", "VARCHAR(32)"),
            ColumnDefinition("connect_result", "VARCHAR(32)"),
            ColumnDefinition("tx_result", "VARCHAR(64)"),
            ColumnDefinition("tx_channel", "VARCHAR(64)"),
            ColumnDefinition("tx_rssi", "VARCHAR(64)"),
            ColumnDefinition("tx_criteria", "VARCHAR(64)"),
            ColumnDefinition("tx_throughput_mbps", "VARCHAR(64)"),
            ColumnDefinition("rx_result", "VARCHAR(64)"),
            ColumnDefinition("rx_channel", "VARCHAR(64)"),
            ColumnDefinition("rx_rssi", "VARCHAR(64)"),
            ColumnDefinition("rx_criteria", "VARCHAR(64)"),
            ColumnDefinition("rx_throughput_mbps", "VARCHAR(64)"),
        ),
        indexes=(
            TableIndex(
                "idx_compat_report",
                "INDEX idx_compat_report (`test_report_id`)",
            ),
            TableIndex(
                "idx_compat_router",
                "INDEX idx_compat_router (`router_id`)",
            ),
        ),
        constraints=(
            TableConstraint(
                "fk_compat_report",
                "CONSTRAINT fk_compat_report FOREIGN KEY (`test_report_id`) REFERENCES `test_report`(`id`)",
            ),
            TableConstraint(
                "fk_compat_router",
                "CONSTRAINT fk_compat_router FOREIGN KEY (`router_id`) REFERENCES `router`(`id`)",
            ),
        ),
    ),
    "performance": TableSpec(
        columns=_PERFORMANCE_BASE_COLUMNS + _PERFORMANCE_EXTRA_COLUMNS,
        indexes=(
            TableIndex(
                "idx_performance_report", "INDEX idx_performance_report (`test_report_id`)"
            ),
            TableIndex(
                "idx_performance_band",
                "INDEX idx_performance_band (`band`, `bandwidth_mhz`, `standard`)",
            ),
            TableIndex(
                "idx_performance_created_at",
                "INDEX idx_performance_created_at (`created_at`)",
            ),
        ),
        constraints=(
            TableConstraint(
                "fk_performance_report",
                "CONSTRAINT fk_performance_report FOREIGN KEY (`test_report_id`) REFERENCES `test_report`(`id`)",
            ),
        ),
    ),
    "perf_metric_kv": TableSpec(
        columns=(
            ColumnDefinition("test_report_id", "INT NOT NULL"),
            ColumnDefinition("metric_name", "VARCHAR(64) NOT NULL"),
            ColumnDefinition("metric_unit", "VARCHAR(16)"),
            ColumnDefinition("metric_value", "DECIMAL(12,4) NOT NULL"),
            ColumnDefinition("stage", "VARCHAR(64)"),
        ),
        indexes=(
            TableIndex(
                "idx_kv_report", "INDEX idx_kv_report (`test_report_id`)"
            ),
            TableIndex(
                "idx_kv_name", "INDEX idx_kv_name (`metric_name`, `stage`)"
            ),
        ),
        constraints=(
            TableConstraint(
                "fk_kv_report",
                "CONSTRAINT fk_kv_report FOREIGN KEY (`test_report_id`) REFERENCES `test_report`(`id`)",
            ),
        ),
    ),
}

_VIEW_DEFINITIONS: Dict[str, str] = {
    "v_run_overview": """
        SELECT
            tr.id AS test_report_id,
            tr.shielded_id,
            tr.dut_id,
            tr.csv_name,
            tr.csv_path,
            tr.data_type,
            tr.case_path,
            tr.created_at AS report_created_at,
            tr.updated_at AS report_updated_at,
            e.case_path AS shielded_case_path,
            e.case_root,
            e.router_name,
            e.router_address,
            e.rf_model,
            e.corner_model,
            e.lab_name,
            d.software_version,
            d.driver_version,
            d.hardware_version,
            d.android_version,
            d.kernel_version,
            d.connect_type,
            d.adb_device,
            d.telnet_ip,
            d.product_line,
            d.project,
            d.main_chip,
            d.wifi_module,
            d.interface,
            agg.throughput_avg_max_mbps,
            agg.throughput_peak_max_mbps,
            agg.throughput_avg_mean_mbps,
            agg.target_throughput_avg_mbps
        FROM test_report AS tr
        LEFT JOIN shielded AS e ON tr.shielded_id = e.id
        LEFT JOIN dut AS d ON tr.dut_id = d.id
        LEFT JOIN (
            SELECT
                test_report_id,
                MAX(throughput_avg_mbps) AS throughput_avg_max_mbps,
                MAX(throughput_peak_mbps) AS throughput_peak_max_mbps,
                AVG(throughput_avg_mbps) AS throughput_avg_mean_mbps,
                AVG(target_throughput_mbps) AS target_throughput_avg_mbps
            FROM performance
            GROUP BY test_report_id
        ) AS agg ON agg.test_report_id = tr.id
    """,
    "v_perf_latest": """
        SELECT
            ranked.id,
            ranked.test_report_id,
            ranked.csv_name,
            ranked.data_type,
            ranked.serial_number,
            ranked.test_category,
            ranked.standard,
            ranked.band,
            ranked.bandwidth_mhz,
            ranked.phy_rate_mbps,
            ranked.center_freq_mhz,
            ranked.protocol,
            ranked.direction,
            ranked.total_path_loss,
            ranked.path_loss_db,
            ranked.rssi,
            ranked.angle_deg,
            ranked.mcs_rate,
            ranked.throughput_peak_mbps,
            ranked.throughput_avg_mbps,
            ranked.target_throughput_mbps,
            ranked.created_at,
            ranked.updated_at,
            ranked.dut_id,
            ranked.report_case_path AS case_path
        FROM (
            SELECT
                p.*,
                tr.dut_id,
                tr.case_path AS report_case_path,
                ROW_NUMBER() OVER (
                    PARTITION BY tr.dut_id, tr.case_path, p.band, p.bandwidth_mhz
                    ORDER BY p.created_at DESC, p.id DESC
                ) AS rn
            FROM performance AS p
            JOIN test_report AS tr ON tr.id = p.test_report_id
        ) AS ranked
        WHERE ranked.rn = 1
    """,
}


def _supports_window_functions(client) -> bool:
    """
    Supports window functions.

    Detects whether the connected MySQL server supports SQL window functions
    such as ROW_NUMBER() OVER (...).  Window functions are available in
    MySQL 8.0 and later.  If the version cannot be determined, this helper
    defaults to ``True`` to preserve existing behaviour.

    Parameters
    ----------
    client : Any
        An object providing a ``query_all`` method compatible with
        :class:`MySqlClient` and :class:`_ConnectionAdapter`.

    Returns
    -------
    bool
        ``True`` if window functions are assumed to be supported, otherwise
        ``False``.
    """
    try:
        rows = client.query_all("SELECT VERSION() AS version")
    except Exception:
        logging.debug("Failed to detect MySQL version for window function support", exc_info=True)
        return True
    if not rows:
        return True
    version_text = str(rows[0].get("version") or "")
    # Expect versions like "5.7.42-0ubuntu0.18.04.1" or "8.0.36"
    match = re.match(r"(\d+)\.(\d+)", version_text)
    if not match:
        return True
    try:
        major = int(match.group(1))
    except ValueError:
        return True
    return major >= 8


def ensure_table(client, table_name: str, spec: TableSpec) -> None:
    """
    Ensure table.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    table_name : Any
        The ``table_name`` parameter.
    spec : Any
        The ``spec`` parameter.

    Returns
    -------
    None
        This function does not return a value.
    """
    if _table_exists(client, table_name):
        return
    _create_table(client, table_name, spec)


def get_table_spec(table_name: str) -> TableSpec:
    """
    Get table spec.

    Parameters
    ----------
    table_name : Any
        The ``table_name`` parameter.

    Returns
    -------
    TableSpec
        A value of type ``TableSpec``.
    """

    try:
        return _TABLE_SPECS[table_name]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise KeyError(f"Unknown table spec: {table_name}") from exc


def ensure_config_tables(client) -> None:
    """
    Ensure config tables.

    Ensures that required tables exist before inserting data.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.

    Returns
    -------
    None
        This function does not return a value.
    """
    ensure_table(client, "dut", _TABLE_SPECS["dut"])
    ensure_table(client, "shielded", _TABLE_SPECS["shielded"])


def ensure_report_tables(client) -> None:
    """
    Ensure report tables.

    Ensures that required tables exist before inserting data.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.

    Returns
    -------
    None
        This function does not return a value.
    """
    ensure_config_tables(client)
    ensure_table(client, "test_report", _TABLE_SPECS["test_report"])
    ensure_table(client, "performance", _TABLE_SPECS["performance"])
    ensure_table(client, "perf_metric_kv", _TABLE_SPECS["perf_metric_kv"])
    ensure_table(client, "router", _TABLE_SPECS["router"])
    ensure_table(client, "compatibility", _TABLE_SPECS["compatibility"])
    _ensure_table_indexes(client, "test_report", _TABLE_SPECS["test_report"].indexes)
    _ensure_table_constraints(client, "test_report", _TABLE_SPECS["test_report"].constraints)
    _ensure_table_indexes(client, "performance", _TABLE_SPECS["performance"].indexes)
    _ensure_table_constraints(client, "performance", _TABLE_SPECS["performance"].constraints)
    _ensure_table_indexes(client, "perf_metric_kv", _TABLE_SPECS["perf_metric_kv"].indexes)
    _ensure_table_constraints(client, "perf_metric_kv", _TABLE_SPECS["perf_metric_kv"].constraints)
    _ensure_table_indexes(client, "router", _TABLE_SPECS["router"].indexes)
    _ensure_table_constraints(client, "router", _TABLE_SPECS["router"].constraints)
    _ensure_table_indexes(client, "compatibility", _TABLE_SPECS["compatibility"].indexes)
    _ensure_table_constraints(client, "compatibility", _TABLE_SPECS["compatibility"].constraints)

    # Best-effort migrations: add missing columns for existing tables.
    _ensure_missing_test_report_columns(client)
    _ensure_views(client)


def _ensure_missing_test_report_columns(client) -> None:
    """Add duration_seconds column to test_report if missing."""
    try:
        cols = client.query_all("SHOW COLUMNS FROM `test_report`")
    except Exception:
        logging.debug("Failed to inspect test_report columns for migration", exc_info=True)
        return
    existing = {str(c.get("Field") or "") for c in cols}
    if "duration_seconds" not in existing:
        try:
            client.execute("ALTER TABLE `test_report` ADD COLUMN `duration_seconds` INT NULL DEFAULT NULL")
        except Exception:
            logging.debug("Failed to add duration_seconds to test_report", exc_info=True)


def _table_exists(client, table_name: str) -> bool:
    """
    Table exists.

    Logs informational messages and errors for debugging purposes.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    table_name : Any
        The ``table_name`` parameter.

    Returns
    -------
    bool
        A value of type ``bool``.
    """
    try:
        rows = client.query_all("SHOW TABLES LIKE %s", (table_name,))
    except Exception:
        logging.debug("Failed to inspect table %s", table_name, exc_info=True)
        return False
    return bool(rows)


def _create_table(client, table_name: str, spec: TableSpec) -> None:
    """
    Create table.

    Runs an SQL statement using a database cursor.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    table_name : Any
        The ``table_name`` parameter.
    spec : Any
        The ``spec`` parameter.

    Returns
    -------
    None
        This function does not return a value.
    """
    all_columns = [ColumnDefinition("id", "INT PRIMARY KEY AUTO_INCREMENT")]
    all_columns.extend(spec.columns)
    if spec.include_audit_columns:
        all_columns.extend(_AUDIT_COLUMNS)
    column_lines = [f"`{column.name}` {column.definition}" for column in all_columns]
    extra_lines = [item.definition for item in spec.indexes] + [
        item.definition for item in spec.constraints
    ]
    lines = column_lines + extra_lines
    statement = (
            f"CREATE TABLE `{table_name}` (\n    "
            + ",\n    ".join(lines)
            + f"\n) ENGINE={spec.engine} DEFAULT CHARSET={spec.charset};"
    )
    client.execute(statement)


def _ensure_index(client, table_name: str, index_name: str, definition: str) -> None:
    """
    Ensure index.

    Runs an SQL statement using a database cursor.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    table_name : Any
        The ``table_name`` parameter.
    index_name : Any
        The ``index_name`` parameter.
    definition : Any
        Column definition string from the table specification.

    Returns
    -------
    None
        This function does not return a value.
    """
    rows = client.query_all(
        f"SHOW INDEX FROM `{table_name}` WHERE Key_name = %s",
        (index_name,),
    )
    if rows:
        return
    client.execute(f"ALTER TABLE `{table_name}` ADD {definition}")


def _ensure_unique(client, table_name: str, constraint: TableConstraint) -> None:
    """
    Ensure unique.

    Runs an SQL statement using a database cursor.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    table_name : Any
        The ``table_name`` parameter.
    constraint : Any
        The ``constraint`` parameter.

    Returns
    -------
    None
        This function does not return a value.
    """
    rows = client.query_all(
        f"SHOW INDEX FROM `{table_name}` WHERE Key_name = %s",
        (constraint.name,),
    )
    if rows:
        return
    client.execute(f"ALTER TABLE `{table_name}` ADD {constraint.definition}")


def _ensure_foreign_key(
        client,
        table_name: str,
        constraint: TableConstraint,
        *,
        delete_rule: str = "RESTRICT",
        update_rule: Optional[str] = None,
) -> None:
    """
    Ensure foreign key.

    Runs an SQL statement using a database cursor.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    table_name : Any
        The ``table_name`` parameter.
    constraint : Any
        The ``constraint`` parameter.

    Returns
    -------
    None
        This function does not return a value.
    """
    rows = client.query_all(
        """
        SELECT rc.DELETE_RULE, rc.UPDATE_RULE
        FROM information_schema.REFERENTIAL_CONSTRAINTS AS rc
        WHERE rc.CONSTRAINT_SCHEMA = DATABASE()
          AND rc.TABLE_NAME = %s
          AND rc.CONSTRAINT_NAME = %s
        """,
        (table_name, constraint.name),
    )
    expected_delete = (delete_rule or "").upper()
    expected_update = (update_rule or "").upper() if update_rule is not None else None
    if not rows:
        client.execute(f"ALTER TABLE `{table_name}` ADD {constraint.definition}")
        return
    current_delete = (rows[0].get("DELETE_RULE") or "").upper()
    current_update = (rows[0].get("UPDATE_RULE") or "").upper()
    needs_replace = False
    if expected_delete and current_delete != expected_delete:
        needs_replace = True
    if expected_update is not None and current_update != expected_update:
        needs_replace = True
    if needs_replace:
        client.execute(f"ALTER TABLE `{table_name}` DROP FOREIGN KEY `{constraint.name}`")
        client.execute(f"ALTER TABLE `{table_name}` ADD {constraint.definition}")


def _ensure_table_indexes(
        client,
        table_name: str,
        indexes: Sequence[TableIndex],
) -> None:
    """
    Ensure table indexes.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    table_name : Any
        The ``table_name`` parameter.
    indexes : Any
        The ``indexes`` parameter.

    Returns
    -------
    None
        This function does not return a value.
    """
    for index in indexes:
        _ensure_index(client, table_name, index.name, index.definition)


def _ensure_table_constraints(
        client,
        table_name: str,
        constraints: Sequence[TableConstraint],
) -> None:
    """
    Ensure table constraints.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    table_name : Any
        The ``table_name`` parameter.
    constraints : Any
        The ``constraints`` parameter.

    Returns
    -------
    None
        This function does not return a value.
    """
    for constraint in constraints:
        normalized = constraint.definition.upper()
        if "FOREIGN KEY" in normalized:
            _ensure_foreign_key(client, table_name, constraint)
        elif "UNIQUE" in normalized:
            _ensure_unique(client, table_name, constraint)


def _ensure_views(client) -> None:
    """
    Ensure views.

    Runs an SQL statement using a database cursor.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.

    Returns
    -------
    None
        This function does not return a value.
    """
    supports_window = _supports_window_functions(client)
    for name, definition in _VIEW_DEFINITIONS.items():
        if name == "v_perf_latest" and not supports_window:
            logging.info(
                "Skipping view %s: requires MySQL 8.0 or later for window functions",
                name,
            )
            continue
        statement = textwrap.dedent(definition).strip()
        if not statement:
            continue
        try:
            client.execute(f"CREATE OR REPLACE VIEW `{name}` AS\n{statement}")
        except Exception:
            logging.exception("Failed to create or replace view %s", name)


def _flatten_section(
        data: Any, builder: IdentifierBuilder, prefix: Tuple[str, ...] = ()
) -> List[Tuple[str, Any, str]]:
    """
    Flatten section.

    Parameters
    ----------
    data : Any
        The ``data`` parameter.
    builder : Any
        The ``builder`` parameter.
    prefix : Any
        The ``prefix`` parameter.

    Returns
    -------
    List[Tuple[str, Any, str]]
        A value of type ``List[Tuple[str, Any, str]]``.
    """
    if isinstance(data, dict):
        items: List[Tuple[str, Any, str]] = []
        for key, value in data.items():
            items.extend(_flatten_section(value, builder, prefix + (str(key),)))
        return items
    path = ".".join(prefix) if prefix else "value"
    column_name = builder.build(prefix or ("value",), fallback="field")
    return [(column_name, data, path)]


def _infer_sql_type(value: Any) -> str:
    """
    Infer SQL type.

    Parameters
    ----------
    value : Any
        Value to sanitize, normalize, or convert.

    Returns
    -------
    str
        A value of type ``str``.
    """
    if isinstance(value, bool):
        return "TINYINT(1)"
    if isinstance(value, int) and not isinstance(value, bool):
        return "BIGINT"
    if isinstance(value, float):
        return "DOUBLE"
    if isinstance(value, (list, tuple, dict)):
        return "JSON"
    return "TEXT"


def _normalize_value(value: Any, sql_type: str) -> Any:
    """
    Normalize value.

    Parameters
    ----------
    value : Any
        Value to sanitize, normalize, or convert.
    sql_type : Any
        The ``sql_type`` parameter.

    Returns
    -------
    Any
        A value of type ``Any``.
    """
    if value is None:
        return None
    if sql_type == "TINYINT(1)":
        return 1 if bool(value) else 0
    if sql_type == "BIGINT":
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if sql_type == "DOUBLE":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if sql_type == "JSON":
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_section_payload(
        section: dict | None,
) -> Tuple[List[ColumnDefinition], List[Any], Dict[str, str]]:
    """
    Build section payload.

    Parameters
    ----------
    section : Any
        The ``section`` parameter.

    Returns
    -------
    Tuple[List[ColumnDefinition], List[Any], Dict[str, str]]
        A value of type ``Tuple[List[ColumnDefinition], List[Any], Dict[str, str]]``.
    """
    if not isinstance(section, dict) or not section:
        return [], [], {}

    builder = IdentifierBuilder()
    flattened = _flatten_section(section, builder)
    columns: List[ColumnDefinition] = []
    values: List[Any] = []
    mapping: Dict[str, str] = {}

    for column_name, raw_value, path in flattened:
        sql_type = _infer_sql_type(raw_value)
        columns.append(ColumnDefinition(column_name, f"{sql_type} NULL DEFAULT NULL"))
        values.append(_normalize_value(raw_value, sql_type))
        mapping[column_name] = path
    return columns, values, mapping


def resolve_case_table_name(
        case_path: Optional[str],
        data_type: Optional[str],
        *,
        log_file_path: Optional[Path] = None,
) -> str:
    """
    Resolve case table name.

    Parameters
    ----------
    case_path : Any
        Path used to derive the target table name for test data.
    data_type : Any
        Logical data type label stored alongside test results.

    Returns
    -------
    str
        A value of type ``str``.
    """
    candidate = None
    if case_path:
        path = Path(case_path)
        candidate = path.parent.name or path.stem
    if not candidate and data_type:
        candidate = data_type
    if not candidate:
        candidate = "test_results"

    base = sanitize_identifier(candidate, fallback="test_results")

    if not log_file_path:
        return base

    stem = sanitize_identifier(log_file_path.stem, fallback="result")
    if not stem or stem == base:
        return base
    return f"{base}_{stem}"


def drop_and_create_table(
        client: "MySqlClient", table_name: str, columns: Sequence[ColumnDefinition]
) -> None:
    """
    Drop and create table.

    Runs an SQL statement using a database cursor.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    table_name : Any
        The ``table_name`` parameter.
    columns : Any
        Sequence of column specifications.

    Returns
    -------
    None
        This function does not return a value.
    """
    client.execute(f"DROP TABLE IF EXISTS `{table_name}`")
    statements = [
        f"CREATE TABLE `{table_name}` (",
        "    id INT PRIMARY KEY AUTO_INCREMENT,",
    ]
    statements.extend(f"    {line}," for line in column_lines)
    if spec.include_audit_columns:
        statements.extend(
            [
                "    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,",
                "    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
            ]
        )
    statements.append(f") ENGINE={spec.engine} DEFAULT CHARSET={spec.charset};")
    create_sql = "\n".join(statements)
    client.execute(create_sql)


def insert_rows(
        client: "MySqlClient",
        table_name: str,
        columns: Sequence[ColumnDefinition],
        rows: Sequence[Sequence[Any]],
) -> List[int]:
    """
    Insert rows.

    Inserts rows into the database and returns the last inserted ID.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    table_name : Any
        The ``table_name`` parameter.
    columns : Any
        Sequence of column specifications.
    rows : Any
        Iterable or sequence of data rows.

    Returns
    -------
    List[int]
        A value of type ``List[int]``.
    """
    if not rows:
        return []
    if not columns:
        return [client.insert(f"INSERT INTO `{table_name}` () VALUES ()") for _ in rows]
    column_names = ", ".join(f"`{column.name}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO `{table_name}` ({column_names}) VALUES ({placeholders})"
    return [client.insert(sql, row) for row in rows]


def read_csv_rows(file_path: Path) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Read CSV rows.

    Reads data from a CSV file and processes each row.

    Parameters
    ----------
    file_path : Any
        The ``file_path`` parameter.

    Returns
    -------
    Tuple[List[str], List[Dict[str, Any]]]
        A value of type ``Tuple[List[str], List[Dict[str, Any]]]``.
    """
    encodings = ("utf-8-sig", "gbk", "utf-8")
    for encoding in encodings:
        try:
            with file_path.open(encoding=encoding, newline="") as handle:
                reader = csv.DictReader(handle)
                headers = reader.fieldnames or []
                rows = [dict(row) for row in reader]
                if headers:
                    return headers, rows
        except UnicodeDecodeError:
            continue
    with file_path.open(encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        rows = [dict(row) for row in reader]
    return headers, rows


def build_header_mappings(headers: Sequence[str]) -> List[HeaderMapping]:
    """
    Build header mappings.

    Parameters
    ----------
    headers : Any
        The ``headers`` parameter.

    Returns
    -------
    List[HeaderMapping]
        A value of type ``List[HeaderMapping]``.
    """
    builder = IdentifierBuilder()
    mappings: List[HeaderMapping] = []
    for header in headers:
        mappings.append(HeaderMapping(header, builder.build((header,), fallback="column")))
    return mappings
