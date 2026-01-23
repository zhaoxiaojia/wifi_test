from __future__ import annotations
import csv
import json
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Mapping, Callable, Tuple

from .client import MySqlClient
from .schema import (
    PERFORMANCE_COLUMN_RENAMES,
    PERFORMANCE_STATIC_COLUMNS,
    ensure_report_tables,
    read_csv_rows,
)
from .sql_writer import SqlWriter
from src.util.constants import (
    TURN_TABLE_FIELD_MODEL,
    TURN_TABLE_SECTION_KEY,
    WIFI_PRODUCT_PROJECT_MAP,
    load_config,
    get_debug_flags,
)

__all__ = [
    "PerformanceTableManager",
    "sync_configuration",
    "sync_test_result_to_db",
    "sync_file_to_db",
    "sync_compatibility_artifacts_to_db",
]

ColumnNormalizer = Callable[[Any], Any]


@dataclass(frozen=True)
class ConfigSyncResult:
    project_id: int


@dataclass(frozen=True)
class _StaticColumn:
    """
    Static column.

    Parameters
    ----------
    None
        This class does not take constructor arguments beyond ``self``.

    Returns
    -------
    None
        This class does not return a value.
    """
    name: str
    sql_type: str
    original: str
    normalizer: Optional[ColumnNormalizer] = None


_ALLOWED_BANDS = {"2.4", "5", "6"}
_ALLOWED_DIRECTIONS = {"uplink", "downlink", "bi"}
_ALLOWED_STANDARDS = [
    "11be",
    "11ax",
    "11ac",
    "11n",
    "11g",
    "11b",
    "11a",
]


def _normalize_band_token(value: Any) -> Optional[str]:
    """
    Normalize band token.

    Parameters
    ----------
    value : Any
        Value to sanitize, normalize, or convert.

    Returns
    -------
    Optional[str]
        A value of type ``Optional[str]``.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in _ALLOWED_BANDS:
        return lowered
    simplified = re.sub(r"[\s_\-]", "", lowered)
    simplified = re.sub(r"ghz$", "", simplified)
    simplified = re.sub(r"g$", "", simplified)
    if simplified in _ALLOWED_BANDS:
        return simplified
    match = re.search(r"2\s*\.\s*4", lowered)
    if match:
        return "2.4"
    match = re.search(r"\b(5|6)\b", lowered)
    if match and match.group(1) in _ALLOWED_BANDS:
        return match.group(1)
    return None


def _normalize_direction_token(value: Any) -> Optional[str]:
    """
    Normalize direction token.

    Parameters
    ----------
    value : Any
        Value to sanitize, normalize, or convert.

    Returns
    -------
    Optional[str]
        A value of type ``Optional[str]``.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in _ALLOWED_DIRECTIONS:
        return text
    mapping = {
        "up": "uplink",
        "uplinked": "uplink",
        "ul": "uplink",
        "down": "downlink",
        "dl": "downlink",
        "downlinked": "downlink",
        "bi-direction": "bi",
        "bidirectional": "bi",
        "bi-directional": "bi",
        "both": "bi",
    }
    return mapping.get(text)


def _normalize_standard_token(value: Any) -> Optional[str]:
    """
    Normalize standard token.

    Parameters
    ----------
    value : Any
        Value to sanitize, normalize, or convert.

    Returns
    -------
    Optional[str]
        A value of type ``Optional[str]``.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in _ALLOWED_STANDARDS:
        return text
    for candidate in _ALLOWED_STANDARDS:
        if candidate in text:
            return candidate
    match = re.search(r"11[a-z]{1,2}", text)
    if match:
        candidate = match.group(0)
        if candidate in _ALLOWED_STANDARDS:
            return candidate
    return None


def _normalize_str_token(value: Any) -> Optional[str]:
    """
    Normalize str token.

    Parameters
    ----------
    value : Any
        Value to sanitize, normalize, or convert.

    Returns
    -------
    Optional[str]
        A value of type ``Optional[str]``.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_lower_token(value: Any) -> Optional[str]:
    """
    Normalize lower token.

    Parameters
    ----------
    value : Any
        Value to sanitize, normalize, or convert.

    Returns
    -------
    Optional[str]
        A value of type ``Optional[str]``.
    """
    text = _normalize_str_token(value)
    return text.lower() if text else None


def _normalize_angle_token(value: Any) -> Optional[float]:
    """
    Normalize angle token.

    Parameters
    ----------
    value : Any
        Value to sanitize, normalize, or convert.

    Returns
    -------
    Optional[float]
        A value of type ``Optional[float]``.
    """
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


_COLUMN_NORMALIZERS: Dict[str, ColumnNormalizer] = {
    "band": _normalize_band_token,
    "direction": _normalize_direction_token,
    "standard": _normalize_standard_token,
    "angle_deg": _normalize_angle_token,
}


class PerformanceTableManager:
    """
    Performance table manager.

    Parameters
    ----------
    None
        This class does not take constructor arguments beyond ``self``.

    Returns
    -------
    None
        This class does not return a value.
    """

    TABLE_NAME = "performance"
    REPORT_TABLE_NAME = "test_report"

    _BASE_COLUMNS: Sequence[tuple[str, str]] = (
        ("execution_id", "INT NOT NULL"),
        ("csv_name", "VARCHAR(255) NOT NULL"),
        ("data_type", "VARCHAR(64) NULL DEFAULT NULL"),
    )

    _STATIC_COLUMNS: Sequence[_StaticColumn] = tuple(
        _StaticColumn(
            name=name,
            sql_type=sql_type,
            original=original,
            normalizer=_COLUMN_NORMALIZERS.get(name),
        )
        for name, sql_type, original in PERFORMANCE_STATIC_COLUMNS
    )

    def __init__(self, client: MySqlClient) -> None:
        """
        Init.

        Parameters
        ----------
        client : Any
            An instance of MySqlClient used to interact with the database.

        Returns
        -------
        None
            This method does not return a value.
        """
        self._client = client

    @staticmethod
    def _classify_value(value: Any) -> tuple[str, Any]:
        """
        Classify value.

        Parameters
        ----------
        value : Any
            Value to sanitize, normalize, or convert.

        Returns
        -------
        tuple[str, Any]
            A value of type ``tuple[str, Any]``.
        """
        if value is None:
            return "empty", None
        if isinstance(value, (dict, list)):
            return "json", value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if isinstance(value, float) and not value.is_integer():
                return "float", float(value)
            return "int", int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return "empty", None
            lowered = stripped.lower()
            if lowered in {"null", "none", "nan"}:
                return "empty", None
            if stripped[0] in {"{", "["}:
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, (dict, list)):
                        return "json", parsed
                except Exception:
                    pass
            for caster, label in ((int, "int"), (float, "float")):
                try:
                    casted = caster(stripped)
                    return label, casted
                except Exception:
                    continue
            return "text", stripped
        return "text", str(value)

    @staticmethod
    def _canonical_sql_type(sql_type: str) -> str:
        """
        Canonical SQL type.

        Parameters
        ----------
        sql_type : Any
            The ``sql_type`` parameter.

        Returns
        -------
        str
            A value of type ``str``.
        """
        normalized = (sql_type or "").upper()
        if normalized.startswith("DECIMAL"):
            return "DECIMAL"
        if normalized.startswith("DOUBLE"):
            return "DOUBLE"
        if normalized.startswith("FLOAT"):
            return "DOUBLE"
        if normalized.startswith("ENUM"):
            return "ENUM"
        if normalized.startswith("JSON"):
            return "JSON"
        if normalized.startswith("BIGINT") or normalized.startswith("INT"):
            return "INT"
        if normalized.startswith("SMALLINT") or normalized.startswith("TINYINT") or normalized.startswith("MEDIUMINT"):
            return "INT"
        if "CHAR" in normalized:
            return "VARCHAR"
        return "TEXT"

    @staticmethod
    def _normalize_cell(value: Any, sql_type: str) -> Any:
        """
        Normalize cell.

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
        value_type, parsed = PerformanceTableManager._classify_value(value)
        if parsed is None:
            return None
        canonical = PerformanceTableManager._canonical_sql_type(sql_type)
        if canonical == "JSON":
            if value_type in {"json", "float", "int"}:
                return json.dumps(parsed, ensure_ascii=False)
            return json.dumps(str(parsed), ensure_ascii=False)
        if canonical == "DOUBLE":
            if value_type in {"float", "int"}:
                return float(parsed)
            return None
        if canonical == "INT":
            if value_type == "int":
                return int(parsed)
            if value_type == "float":
                float_value = float(parsed)
                if float_value.is_integer():
                    return int(float_value)
            return None
        if canonical == "DECIMAL":
            if value_type in {"float", "int"}:
                return Decimal(str(parsed))
            if value_type == "text":
                try:
                    return Decimal(str(parsed))
                except InvalidOperation:
                    return None
            return None
        if canonical == "ENUM":
            return str(parsed)
        return str(parsed)

    def _describe_columns(self) -> Dict[str, Dict[str, Any]]:
        """
        Describe columns.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        Dict[str, Dict[str, Any]]
            A value of type ``Dict[str, Dict[str, Any]]``.
        """
        return {
            column["Field"]: column
            for column in self._client.query_all(f"SHOW FULL COLUMNS FROM `{self.TABLE_NAME}`")
        }

    def _ensure_static_columns(self) -> None:
        """
        Ensure static columns.

        Runs an SQL statement using a database cursor.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        None
            This method does not return a value.
        """
        snapshot = self._describe_columns()
        snapshot = self._apply_column_renames(snapshot)
        for column in self._STATIC_COLUMNS:
            definition = self._format_column_definition(column)
            if column.name not in snapshot:
                self._client.execute(
                    f"ALTER TABLE `{self.TABLE_NAME}` "
                    f"ADD COLUMN `{column.name}` {definition}"
                )
                snapshot = self._describe_columns()
                continue
            self._client.execute(
                f"ALTER TABLE `{self.TABLE_NAME}` "
                f"MODIFY COLUMN `{column.name}` {definition}"
            )

    def _apply_column_renames(
            self, snapshot: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Apply column renames.

        Runs an SQL statement using a database cursor.

        Parameters
        ----------
        snapshot : Any
            The ``snapshot`` parameter.

        Returns
        -------
        Dict[str, Dict[str, Any]]
            A value of type ``Dict[str, Dict[str, Any]]``.
        """
        updated = snapshot
        for old_name, new_name in PERFORMANCE_COLUMN_RENAMES:
            if old_name in updated and new_name not in updated:
                self._client.execute(
                    f"ALTER TABLE `{self.TABLE_NAME}` "
                    f"RENAME COLUMN `{old_name}` TO `{new_name}`"
                )
                updated = self._describe_columns()
        return updated

    @staticmethod
    def _collect_throughput_headers(headers: Sequence[str]) -> List[str]:
        """
        Collect throughput headers.

        Parameters
        ----------
        headers : Any
            The ``headers`` parameter.

        Returns
        -------
        List[str]
            A value of type ``List[str]``.
        """
        aliases: List[str] = []
        for header in headers:
            if header is None:
                continue
            text = str(header).strip()
            if not text:
                continue
            if text.lower().startswith("throughput"):
                aliases.append(text)
        return aliases

    @staticmethod
    def _parse_throughput_value(value: Any) -> List[float]:
        """
        Parse throughput value.

        Parameters
        ----------
        value : Any
            Value to sanitize, normalize, or convert.

        Returns
        -------
        List[float]
            A value of type ``List[float]``.
        """
        if value is None:
            return []
        if isinstance(value, (int, float, Decimal)):
            return [float(value)]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            numbers: List[float] = []
            tokens = re.split(r"[,\s]+", text)
            for token in tokens:
                if not token:
                    continue
                try:
                    numbers.append(float(token))
                except Exception:
                    continue
            if numbers:
                return numbers
            try:
                return [float(text)]
            except Exception:
                return []
        return []

    @classmethod
    def _compute_throughput_average(cls, values: Sequence[Any]) -> Optional[float]:
        """
        Compute throughput average.

        Parameters
        ----------
        values : Any
            The ``values`` parameter.

        Returns
        -------
        Optional[float]
            A value of type ``Optional[float]``.
        """
        samples: List[float] = []
        for value in values:
            samples.extend(cls._parse_throughput_value(value))
        if not samples:
            return None
        return sum(samples) / len(samples)

    @staticmethod
    def _format_column_definition(column: _StaticColumn) -> str:
        """
        Format column definition.

        Parameters
        ----------
        column : Any
            Column specification object.

        Returns
        -------
        str
            A value of type ``str``.
        """
        comment = column.original.replace("'", "''")
        return f"{column.sql_type} NULL DEFAULT NULL COMMENT '{comment}'"

    def _register_execution(
            self,
            *,
            project_payload: Mapping[str, Any],
            execution_payload: Mapping[str, Any],
            csv_name: str,
            csv_path: str,
            data_type: Optional[str],
            case_path: Optional[str],
            run_source: str,
            duration_seconds: Optional[float] = None,
    ) -> int:
        """
        Register execution.

        Inserts rows into the database and returns the last inserted ID.
        Reads data from a CSV file and processes each row.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        int
            A value of type ``int``.
        """
        execution_type = (data_type or "PERFORMANCE").strip().upper()
        report_name = execution_type
        return register_execution(
            self._client,
            project_payload=project_payload,
            report_name=report_name,
            case_path=case_path,
            execution_type=execution_type,
            execution_payload=execution_payload,
            csv_name=csv_name,
            csv_path=csv_path,
            run_source=run_source,
            duration_seconds=duration_seconds,
        )

    def ensure_schema_initialized(self) -> None:
        """
        Ensure schema initialized.

        Ensures that required tables exist before inserting data.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        None
            This method does not return a value.
        """
        ensure_report_tables(self._client)
        self._ensure_static_columns()

    def replace_with_csv(
            self,
            *,
            csv_name: str,
            csv_path: str,
            headers: Sequence[str],
            rows: Sequence[Dict[str, Any]],
            data_type: Optional[str],
            run_source: str,
            case_path: Optional[str],
            project_payload: Mapping[str, Any],
            execution_payload: Mapping[str, Any],
            duration_seconds: Optional[float] = None,
    ) -> int:
        """
        Replace with CSV.

        Executes multiple SQL statements in a batch using a cursor.
        Reads data from a CSV file and processes each row.
        Logs informational messages and errors for debugging purposes.

        Parameters
        ----------
        None
            This method does not accept any additional parameters beyond ``self``.

        Returns
        -------
        int
            A value of type ``int``.
        """
        logging.info(
            "Sync CSV %s into performance table | headers=%s rows=%s",
            csv_name,
            len(headers),
            len(rows),
        )

        self.ensure_schema_initialized()

        execution_id = self._register_execution(
            project_payload=project_payload,
            execution_payload=execution_payload,
            csv_name=csv_name,
            csv_path=csv_path,
            data_type=data_type,
            case_path=case_path,
            run_source=run_source,
            duration_seconds=duration_seconds,
        )
        logging.debug("Created execution entry id=%s", execution_id)

        insert_columns = [name for name, _ in self._BASE_COLUMNS]
        insert_columns.extend(column.name for column in self._STATIC_COLUMNS)
        writer = SqlWriter(self.TABLE_NAME)
        insert_sql = writer.insert_statement(insert_columns)

        throughput_aliases = self._collect_throughput_headers(headers)
        values: List[List[Any]] = []
        for row in rows:
            row_values: List[Any] = [
                execution_id,
                csv_name,
                data_type,
            ]
            for column in self._STATIC_COLUMNS:
                if column.original == "Throughput":
                    samples: List[Any] = []
                    if throughput_aliases:
                        for alias in throughput_aliases:
                            value = row.get(alias)
                            if value is not None:
                                samples.append(value)
                    else:
                        value = row.get(column.original)
                        if value is not None:
                            samples.append(value)
                    raw_value = self._compute_throughput_average(samples)
                else:
                    raw_value = row.get(column.original)
                if column.normalizer is not None:
                    try:
                        raw_value = column.normalizer(raw_value)
                    except Exception:
                        logging.debug(
                            "Failed to normalize column %s with value %s",
                            column.name,
                            raw_value,
                            exc_info=True,
                        )
                row_values.append(
                    self._normalize_cell(raw_value, column.sql_type)
                )
            values.append(row_values)

        affected_total = 0
        if values:
            affected_total = self._client.executemany(insert_sql, values)
            if affected_total != len(values):
                logging.warning(
                    "Expected to insert %s rows but database reported %s",
                    len(values),
                    affected_total,
                )
            else:
                logging.info(
                    "Stored %s rows from %s into %s",
                    affected_total,
                    csv_name,
                    self.TABLE_NAME,
                )
        else:
            logging.info("CSV %s contains no rows; only metadata recorded.", csv_name)

        return affected_total


def _extract_first(mapping: Mapping[str, Any] | None, *keys: str) -> Optional[Any]:
    """
    Extract first.

    Parameters
    ----------
    mapping : Any
        The ``mapping`` parameter.

    Returns
    -------
    Optional[Any]
        A value of type ``Optional[Any]``.
    """
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _normalize_upper_token(value: Any) -> Optional[str]:
    """
    Normalize upper token.

    Parameters
    ----------
    value : Any
        Value to sanitize, normalize, or convert.

    Returns
    -------
    Optional[str]
        A value of type ``Optional[str]``.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.upper()


def _split_fpga(value: Any) -> tuple[Optional[str], Optional[str]]:
    """Split project/fpga configuration into wifi_module and interface."""
    if isinstance(value, Mapping):
        module_value = value.get("wifi_module", value.get("series"))
        interface_value = value.get("interface")
        return _normalize_upper_token(module_value), _normalize_upper_token(interface_value)
    if isinstance(value, str):
        parts = value.split("_", 1)
        module = _normalize_upper_token(parts[0]) if parts and parts[0] else None
        interface = _normalize_upper_token(parts[1]) if len(parts) > 1 else None
        return module, interface
    return None, None


def _guess_product_by_mapping(
        wifi_module: Optional[str],
        interface: Optional[str],
        main_chip: Optional[str],
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[dict[str, str]]]:
    """
    Guess product by mapping.

    Parameters
    ----------
    wifi_module : Any
        The ``wifi_module`` parameter.
    interface : Any
        The ``interface`` parameter.
    main_chip : Any
        The ``main_chip`` parameter.

    Returns
    -------
    tuple[Optional[str], Optional[str], Optional[str], Optional[dict[str, str]]]
        A value of type ``tuple[Optional[str], Optional[str], Optional[str], Optional[dict[str, str]]]``.
    """
    wifi_upper = _normalize_upper_token(wifi_module)
    interface_upper = _normalize_upper_token(interface)
    chip_upper = _normalize_upper_token(main_chip)

    for customer_name, product_lines in WIFI_PRODUCT_PROJECT_MAP.items():
        for product_line, projects in product_lines.items():
            for project_name, info in projects.items():
                info_wifi = _normalize_upper_token(info.get("wifi_module"))
                info_interface = _normalize_upper_token(info.get("interface"))
                info_chip = _normalize_upper_token(info.get("main_chip"))
                if wifi_upper and info_wifi and info_wifi != wifi_upper:
                    continue
                if interface_upper and info_interface and info_interface != interface_upper:
                    continue
                if chip_upper and info_chip and info_chip != chip_upper:
                    continue
                return customer_name, product_line, project_name, info
    return None, None, None, None


def _resolve_wifi_product_details(fpga_section: Any) -> Dict[str, Optional[str]]:
    """
    Resolve wifi product details.

    Parameters
    ----------
    fpga_section : Any
        The ``fpga_section`` parameter.

    Returns
    -------
    Dict[str, Optional[str]]
        A value of type ``Dict[str, Optional[str]]``.
    """
    details: Dict[str, Optional[str]] = {
        "customer": None,
        "product_line": None,
        "project": None,
        "main_chip": None,
        "wifi_module": None,
        "interface": None,
        "ecosystem": None,
    }

    if isinstance(fpga_section, Mapping):
        details["customer"] = _normalize_upper_token(fpga_section.get("customer"))
        details["product_line"] = _normalize_upper_token(fpga_section.get("product_line"))
        details["project"] = _normalize_upper_token(fpga_section.get("project"))
        details["main_chip"] = _normalize_upper_token(fpga_section.get("main_chip"))
        details["wifi_module"] = _normalize_upper_token(
            fpga_section.get("wifi_module") or fpga_section.get("series")
        )
        details["interface"] = _normalize_upper_token(fpga_section.get("interface"))
    else:
        wifi_module, interface = _split_fpga(fpga_section)
        details["wifi_module"] = wifi_module
        details["interface"] = interface

    info: Optional[dict[str, str]] = None
    if details["customer"] and details["product_line"] and details["project"]:
        info = (
            WIFI_PRODUCT_PROJECT_MAP.get(details["customer"], {})
            .get(details["product_line"], {})
            .get(details["project"], {})
        )
    elif details["product_line"] and details["project"]:
        for customer_name, product_lines in WIFI_PRODUCT_PROJECT_MAP.items():
            project_info = product_lines.get(details["product_line"], {}).get(details["project"])
            if project_info:
                details["customer"] = customer_name
                info = project_info
                break
    if info is None:
        (
            guessed_customer,
            guessed_product,
            guessed_project,
            guessed_info,
        ) = _guess_product_by_mapping(
            details["wifi_module"],
            details["interface"],
            details["main_chip"],
        )
        if guessed_customer:
            details["customer"] = guessed_customer
        if guessed_product:
            details["product_line"] = guessed_product
        if guessed_project:
            details["project"] = guessed_project
        info = guessed_info

    if info:
        if not details["main_chip"]:
            details["main_chip"] = _normalize_upper_token(info.get("main_chip"))
        if not details["wifi_module"]:
            details["wifi_module"] = _normalize_upper_token(info.get("wifi_module"))
        if not details["interface"]:
            details["interface"] = _normalize_upper_token(info.get("interface"))
        if not details["ecosystem"]:
            details["ecosystem"] = _normalize_upper_token(info.get("ecosystem"))

    return details


def _build_project_payload(config: Mapping[str, Any]) -> Dict[str, Any]:
    fpga_section = _extract_first(config, "project", "fpga")
    wifi_details = _resolve_wifi_product_details(fpga_section)
    payload_json = json.dumps(wifi_details, ensure_ascii=True, separators=(",", ":"))
    return {
        "brand": wifi_details.get("customer"),
        "product_line": wifi_details.get("product_line"),
        "project_name": wifi_details.get("project"),
        "main_chip": wifi_details.get("main_chip"),
        "wifi_module": wifi_details.get("wifi_module"),
        "interface": wifi_details.get("interface"),
        "ecosystem": wifi_details.get("ecosystem"),
        "payload_json": payload_json,
    }


def ensure_project(client: MySqlClient, project_payload: Mapping[str, Any]) -> int:
    insert_sql = (
        "INSERT INTO `project` "
        "(`brand`, `product_line`, `project_name`, `main_chip`, `wifi_module`, `interface`, `ecosystem`, `payload_json`) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "`id`=LAST_INSERT_ID(`id`), "
        "`main_chip`=VALUES(`main_chip`), "
        "`wifi_module`=VALUES(`wifi_module`), "
        "`interface`=VALUES(`interface`), "
        "`ecosystem`=VALUES(`ecosystem`), "
        "`payload_json`=VALUES(`payload_json`)"
    )
    return client.insert(
        insert_sql,
        (
            project_payload.get("brand"),
            project_payload.get("product_line"),
            project_payload.get("project_name"),
            project_payload.get("main_chip"),
            project_payload.get("wifi_module"),
            project_payload.get("interface"),
            project_payload.get("ecosystem"),
            project_payload.get("payload_json"),
        ),
    )


def ensure_test_report(
    client: MySqlClient,
    *,
    project_id: int,
    report_name: str,
    case_path: Optional[str],
) -> int:
    insert_sql = (
        "INSERT INTO `test_report` "
        "(`project_id`, `report_name`, `case_path`) "
        "VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "`id`=LAST_INSERT_ID(`id`), "
        "`case_path`=VALUES(`case_path`)"
    )
    return client.insert(insert_sql, (project_id, report_name, case_path))


def register_execution(
    client: MySqlClient,
    *,
    project_payload: Mapping[str, Any],
    report_name: str,
    case_path: Optional[str],
    execution_type: str,
    execution_payload: Mapping[str, Any],
    csv_name: str,
    csv_path: str,
    run_source: str,
    duration_seconds: Optional[float] = None,
) -> int:
    project_id = ensure_project(client, project_payload)
    test_report_id = ensure_test_report(
        client,
        project_id=project_id,
        report_name=report_name,
        case_path=case_path,
    )
    insert_sql = (
        "INSERT INTO `execution` "
        "(`test_report_id`, `execution_type`, `serial_number`, `connect_type`, `adb_device`, `telnet_ip`, "
        "`software_version`, `driver_version`, `hardware_version`, `android_version`, `kernel_version`, "
        "`router_name`, `router_address`, `rf_model`, `corner_model`, `lab_name`, "
        "`csv_name`, `csv_path`, `run_source`, `duration_seconds`, `payload_json`) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    payload_json = json.dumps(dict(execution_payload), ensure_ascii=True, separators=(",", ":"))
    return client.insert(
        insert_sql,
        (
            test_report_id,
            execution_type,
            execution_payload.get("serial_number"),
            execution_payload.get("connect_type"),
            execution_payload.get("adb_device"),
            execution_payload.get("telnet_ip"),
            execution_payload.get("software_version"),
            execution_payload.get("driver_version"),
            execution_payload.get("hardware_version"),
            execution_payload.get("android_version"),
            execution_payload.get("kernel_version"),
            execution_payload.get("router_name"),
            execution_payload.get("router_address"),
            execution_payload.get("rf_model"),
            execution_payload.get("corner_model"),
            execution_payload.get("lab_name"),
            csv_name,
            csv_path,
            run_source,
            int(duration_seconds) if duration_seconds is not None else None,
            payload_json,
        ),
    )


def _extract_serial_number(config: Mapping[str, Any]) -> Optional[str]:
    hardware_section = _extract_first(config, "hardware_info", "hardware")
    hardware = hardware_section if isinstance(hardware_section, Mapping) else {}
    return _normalize_str_token(
        _extract_first(hardware, "serial_number", "serial", "sn", "serialnumber")
        or config.get("serial_number")
        or config.get("serial")
    )


def _build_execution_device_payload(config: Mapping[str, Any]) -> Dict[str, Any]:
    software_section = _extract_first(config, "software_info", "software")
    software = software_section if isinstance(software_section, Mapping) else {}
    hardware_section = _extract_first(config, "hardware_info", "hardware")
    hardware = hardware_section if isinstance(hardware_section, Mapping) else {}
    android_section = _extract_first(config, "android_system", "system", "android")
    android = android_section if isinstance(android_section, Mapping) else {}
    connect_section = _extract_first(config, "connect_type", "connect")
    connect = connect_section if isinstance(connect_section, Mapping) else {}

    connect_type_value = _normalize_str_token(connect.get("type"))
    normalized_connect_type = _normalize_lower_token(connect_type_value)
    if normalized_connect_type == "android":
        connect_type_value = "Android"
    elif normalized_connect_type == "linux":
        connect_type_value = "Linux"

    adb_device: Optional[str] = None
    telnet_ip: Optional[str] = None

    if normalized_connect_type == "android":
        adb_device = _normalize_str_token(_extract_first(connect, "Android", "device"))
    elif normalized_connect_type == "linux":
        telnet_ip = _normalize_str_token(_extract_first(connect, "Linux", "ip"))

    return {
        "serial_number": _extract_serial_number(config),
        "software_version": _extract_first(software, "software_version"),
        "driver_version": _extract_first(software, "driver_version"),
        "hardware_version": _extract_first(hardware, "hardware_version"),
        "android_version": _extract_first(android, "version"),
        "kernel_version": _extract_first(android, "kernel_version"),
        "connect_type": connect_type_value,
        "adb_device": adb_device,
        "telnet_ip": telnet_ip,
    }


def _build_execution_lab_payload(config: Mapping[str, Any]) -> Dict[str, Any]:
    router_section = _extract_first(config, "router")
    router = router_section if isinstance(router_section, Mapping) else {}
    rf_solution = config.get("rf_solution") if isinstance(config, Mapping) else {}
    corner_cfg = config.get(TURN_TABLE_SECTION_KEY) if isinstance(config, Mapping) else {}
    lab_info = config.get("lab") if isinstance(config, Mapping) else {}
    flags = get_debug_flags(config=config) if isinstance(config, Mapping) else None
    skip_router = bool(getattr(flags, "skip_router", False))
    skip_corner_rf = bool(getattr(flags, "skip_corner_rf", False))

    if isinstance(rf_solution, Mapping) and not skip_corner_rf:
        rf_model = _normalize_str_token(rf_solution.get("model"))
    else:
        rf_model = None
    if isinstance(corner_cfg, Mapping) and not skip_corner_rf:
        corner_model = _normalize_str_token(corner_cfg.get(TURN_TABLE_FIELD_MODEL))
    else:
        corner_model = None
    if skip_router:
        router_name = None
        router_address = None
    else:
        router_name = _normalize_str_token(router.get("name"))
        router_address = _normalize_str_token(router.get("address"))
    lab_name = None
    if isinstance(config, Mapping):
        lab_name = config.get("lab_name")
    if lab_name is None and isinstance(lab_info, Mapping):
        lab_name_value = lab_info.get("name")
        if isinstance(lab_name_value, str):
            lab_name = _normalize_str_token(lab_name_value)
        else:
            lab_name = None
    elif isinstance(lab_name, str):
        lab_name = _normalize_str_token(lab_name)
    else:
        lab_name = None

    return {
        "router_name": router_name,
        "router_address": router_address,
        "rf_model": rf_model,
        "corner_model": corner_model,
        "lab_name": lab_name,
    }


def _build_execution_payload(config: Mapping[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    payload.update(_build_execution_device_payload(config))
    payload.update(_build_execution_lab_payload(config))
    return payload


def _resolve_case_path(config: Mapping[str, Any]) -> Optional[str]:
    return _normalize_str_token(
        config.get("case_path")
        or config.get("test_case")
        or config.get("text_case")
        or config.get("testcase")
    )


def sync_configuration(config: dict | None) -> Optional[Any]:
    """
    Sync configuration.

    Parameters
    ----------
    config : Any
        Dictionary containing MySQL configuration parameters.

    Returns
    -------
    Optional[Any]
        A value of type ``Optional[Any]``.
    """

    if not isinstance(config, Mapping) or not config:
        return None
    project_payload = _build_project_payload(config)
    with MySqlClient() as client:
        ensure_report_tables(client)
        project_id = ensure_project(client, project_payload)
    return ConfigSyncResult(project_id=project_id)


def sync_test_result_to_db(
        config: dict | None,
        *,
        log_file: str,
        data_type: Optional[str] = None,
        case_path: Optional[str] = None,
        run_source: str = "local",
        duration_seconds: Optional[float] = None,
) -> int:
    """
    Sync test result to db.

    Loads configuration settings from a YAML or configuration file.
    Reads data from a CSV file and processes each row.
    Logs informational messages and errors for debugging purposes.

    Parameters
    ----------
    config : Any
        Dictionary containing MySQL configuration parameters.

    Returns
    -------
    int
        A value of type ``int``.
    """

    active_config: Optional[Mapping[str, Any]] = None
    if isinstance(config, Mapping) and config:
        active_config = config
    else:
        try:
            active_config = load_config(refresh=True)
        except Exception:
            logging.debug(
                "sync_test_result_to_db: failed to load configuration for persistence",
                exc_info=True,
            )
            active_config = None

    if active_config:
        project_payload = _build_project_payload(active_config)
        execution_payload = _build_execution_payload(active_config)
        resolved_case_path = case_path or _resolve_case_path(active_config)
    else:
        logging.debug("sync_test_result_to_db: no configuration available for database sync.")
        project_payload = {}
        execution_payload = {}
        resolved_case_path = case_path

    file_path = Path(log_file)
    if not file_path.is_file():
        logging.error("Log file %s not found, skip syncing test results.", log_file)
        return 0

    headers, rows = read_csv_rows(file_path)
    logging.info(
        "Loaded CSV %s | header_count=%s row_count=%s",
        file_path,
        len(headers),
        len(rows),
    )
    if not headers:
        logging.warning("CSV file %s does not contain a header row.", log_file)

    normalized_data_type = data_type.strip().upper() if isinstance(data_type, str) else None
    normalized_source = (run_source or "local").strip() or "local"
    normalized_source = normalized_source.upper()[:32]

    if normalized_data_type in {"RVR", "RVO"}:
        try:
            from src.tools.performance import generate_rvr_charts
        except Exception:
            logging.exception(
                "sync_test_result_to_db: unable to import chart generator for %s", normalized_data_type
            )
        else:
            try:
                charts_subdir = 'rvo_charts' if normalized_data_type == 'RVO' else 'rvr_charts'
                generated = generate_rvr_charts(file_path, charts_subdir=charts_subdir)
            except Exception:
                logging.exception(
                    "sync_test_result_to_db: failed to auto-generate %s charts for %s",
                    normalized_data_type,
                    file_path,
                )
            else:
                if generated:
                    charts_dir = Path(generated[0]).parent
                    logging.info(
                        "sync_test_result_to_db: saved %d %s chart image(s) under %s",
                        len(generated),
                        normalized_data_type,
                        charts_dir,
                    )
                else:
                    logging.warning(
                        "sync_test_result_to_db: no chart images were produced for %s (%s)",
                        normalized_data_type,
                        file_path,
                    )

    try:
        with MySqlClient() as client:
            manager = PerformanceTableManager(client)
            manager.ensure_schema_initialized()
            affected = manager.replace_with_csv(
                csv_name=file_path.name,
                csv_path=str(file_path),
                headers=headers,
                rows=rows,
                data_type=normalized_data_type,
                run_source=normalized_source,
                case_path=resolved_case_path,
                project_payload=project_payload,
                execution_payload=execution_payload,
                duration_seconds=duration_seconds,
            )
        return affected
    except Exception:
        logging.exception("Failed to sync CSV results into performance table")
        return 0


def sync_compatibility_artifacts_to_db(
        config: dict | None,
        *,
        csv_file: str,
        router_json: str,
        case_path: Optional[str] = None,
        run_source: str = "local",
        duration_seconds: Optional[float] = None,
) -> int:
    """
    Sync compatibility CSV + router catalogue into database.

    Inserts/updates router entries into `router`, registers an execution,
    then bulk inserts rows into `compatibility` linked by `execution_id`
    and `router_id`.
    """
    if not isinstance(config, Mapping) or not config:
        logging.debug("sync_compatibility_artifacts_to_db: skipped, config missing")
        return 0
    project_payload = _build_project_payload(config)
    execution_payload = _build_execution_payload(config)
    resolved_case_path = case_path or _resolve_case_path(config)
    normalized_source = (run_source or "local").strip().upper()[:32]

    with MySqlClient() as client:
        ensure_report_tables(client)

        with open(router_json, "r", encoding="utf-8") as handle:
            router_entries = json.load(handle) or []

        upsert_sql = (
            "INSERT INTO `router` (`ip`, `port`, `brand`, `model`, `payload_json`) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "`brand`=VALUES(`brand`), `model`=VALUES(`model`), `payload_json`=VALUES(`payload_json`)"
        )
        router_rows = []
        for entry in router_entries:
            ip = str(entry.get("ip") or "").strip()
            port = int(str(entry.get("port") or "0").strip() or 0)
            if not ip or port <= 0:
                continue
            brand = str(entry.get("brand") or "").strip()
            model = str(entry.get("model") or "").strip()
            payload_json = json.dumps(entry, ensure_ascii=True, separators=(",", ":"))
            router_rows.append((ip, port, brand, model, payload_json))
        if router_rows:
            client.executemany(upsert_sql, router_rows)

        routers = client.query_all("SELECT id, ip, port FROM `router`")
        router_id_by_key = {
            (str(r.get("ip") or "").strip(), int(r.get("port") or 0)): int(r["id"])
            for r in routers
            if r.get("id") is not None
        }

        execution_id = register_execution(
            client,
            project_payload=project_payload,
            report_name="COMPATIBILITY",
            case_path=resolved_case_path,
            execution_type="COMPATIBILITY",
            execution_payload=execution_payload,
            csv_name=Path(csv_file).name,
            csv_path=str(Path(csv_file).resolve()),
            run_source=normalized_source,
            duration_seconds=duration_seconds,
        )

        with open(csv_file, "r", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            rows = list(reader)

        if not rows or len(rows) < 2:
            return 0

        data_rows = rows[1:]
        insert_cols = [
            "execution_id",
            "router_id",
            "pdu_ip",
            "pdu_port",
            "ap_brand",
            "band",
            "ssid",
            "wifi_mode",
            "bandwidth",
            "security",
            "scan_result",
            "connect_result",
            "tx_result",
            "tx_channel",
            "tx_rssi",
            "tx_criteria",
            "tx_throughput_mbps",
            "rx_result",
            "rx_channel",
            "rx_rssi",
            "rx_criteria",
            "rx_throughput_mbps",
        ]
        placeholders = ", ".join(["%s"] * len(insert_cols))
        insert_sql = f"INSERT INTO `compatibility` ({', '.join(f'`{c}`' for c in insert_cols)}) VALUES ({placeholders})"

        compat_rows = []
        for row in data_rows:
            if not row or len(row) < 4:
                continue
            pdu_ip = str(row[0]).strip()
            pdu_port = int(str(row[1]).strip() or 0)
            ap_brand = str(row[2]).strip() if len(row) > 2 else ""
            band = str(row[3]).strip() if len(row) > 3 else ""
            ssid = str(row[4]).strip() if len(row) > 4 else ""
            wifi_mode = str(row[5]).strip() if len(row) > 5 else ""
            bandwidth = str(row[6]).strip() if len(row) > 6 else ""
            security = str(row[7]).strip() if len(row) > 7 else ""
            scan_result = str(row[8]).strip() if len(row) > 8 else ""
            connect_result = str(row[9]).strip() if len(row) > 9 else ""
            tx_result = str(row[10]).strip() if len(row) > 10 else ""
            tx_channel = str(row[11]).strip() if len(row) > 11 else ""
            tx_rssi = str(row[12]).strip() if len(row) > 12 else ""
            tx_criteria = str(row[13]).strip() if len(row) > 13 else ""
            tx_thr = str(row[14]).strip() if len(row) > 14 else ""
            rx_result = str(row[15]).strip() if len(row) > 15 else ""
            rx_channel = str(row[16]).strip() if len(row) > 16 else ""
            rx_rssi = str(row[17]).strip() if len(row) > 17 else ""
            rx_criteria = str(row[18]).strip() if len(row) > 18 else ""
            rx_thr = str(row[19]).strip() if len(row) > 19 else ""

            router_id = router_id_by_key.get((pdu_ip, pdu_port))
            compat_rows.append(
                (
                    execution_id,
                    router_id,
                    pdu_ip,
                    pdu_port,
                    ap_brand,
                    band,
                    ssid,
                    wifi_mode,
                    bandwidth,
                    security,
                    scan_result,
                    connect_result,
                    tx_result,
                    tx_channel,
                    tx_rssi,
                    tx_criteria,
                    tx_thr,
                    rx_result,
                    rx_channel,
                    rx_rssi,
                    rx_criteria,
                    rx_thr,
                )
            )

        if not compat_rows:
            return 0
        affected = client.executemany(insert_sql, compat_rows)
        logging.info("Synced %s compatibility rows into DB", affected)
        return affected


def sync_file_to_db(
        file_path: str,
        data_type: str,
        *,
        config: Optional[dict] = None,
        case_path: Optional[str] = None,
        run_source: str = "FRAMEWORK",
        duration_seconds: Optional[float] = None,
) -> int:
    """
    Sync file to db.

    Parameters
    ----------
    file_path : Any
        The ``file_path`` parameter.
    data_type : Any
        Logical data type label stored alongside test results.

    Returns
    -------
    int
        A value of type ``int``.
    """

    return sync_test_result_to_db(
        config or {},
        log_file=file_path,
        data_type=data_type,
        case_path=case_path,
        run_source=run_source,
        duration_seconds=duration_seconds,
    )
