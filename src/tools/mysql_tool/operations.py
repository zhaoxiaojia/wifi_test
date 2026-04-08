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
    AP_MODEL_CHOICES,
    AP_REGION_CHOICES,
    BASIC_CONFIG_FILENAME,
    BT_DEVICE_CHOICES,
    BT_REMOTE_CHOICES,
    BT_TYPE_CHOICES,
    DUT_OS_CHOICES,
    LAB_CAPABILITY_CHOICES,
    LAB_ENV_COEX_MODE_CHOICES,
    LAB_NAME_CHOICES,
    LAB_ENV_CONNECT_TYPE_CHOICES,
    LAB_CATALOG,
    HW_PHASE_CHOICES,
    PROJECT_TYPES,
    RUN_TYPE_CHOICES,
    RUN_TYPE_WIFI_SMARTTEST,
    TEST_REPORT_CHOICES,
    TEST_REPORT_COMPATIBILITY,
    TEST_REPORT_PEAK_THROUGHPUT,
    TEST_REPORT_RVO,
    TEST_REPORT_RVR,
    TURN_TABLE_FIELD_MODEL,
    TURN_TABLE_SECTION_KEY,
    WIFI_PRODUCT_PROJECT_MAP,
    Paths,
    get_config_base,
    load_config,
    get_debug_flags,
)


def _require_test_report_type(value: str | None) -> str:
    report_type = str(value or "").strip()
    if report_type not in TEST_REPORT_CHOICES:
        raise ValueError(
            f"Unsupported test_report type={report_type!r}; "
            f"allowed={list(TEST_REPORT_CHOICES)!r}"
        )
    return report_type


def _require_run_type(value: str | None) -> str:
    run_type = str(value or "").strip()
    if run_type not in RUN_TYPE_CHOICES:
        raise ValueError(
            f"Unsupported execution.run_type={run_type!r}; "
            f"allowed={list(RUN_TYPE_CHOICES)!r}"
        )
    return run_type

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
    "wifi_mode": _normalize_standard_token,
    "angle": _normalize_angle_token,
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
        ("test_report_id", "INT NOT NULL"),
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
        execution_type = str(data_type or "").strip()
        report_name = str(csv_name or execution_type)
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
            execution_type: Optional[str],
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
            data_type=execution_type,
            case_path=case_path,
            run_source=run_source,
            duration_seconds=duration_seconds,
        )
        logging.info("[DBTRACE_EXEC] replace_with_csv execution_id=%s", execution_id)
        test_report_id = int(
            self._client.query_one(
                "SELECT `test_report_id` FROM `execution` WHERE `id`=%s LIMIT 1",
                (execution_id,),
            )["test_report_id"]
        )

        insert_columns = [name for name, _ in self._BASE_COLUMNS]
        insert_columns.extend(column.name for column in self._STATIC_COLUMNS)
        writer = SqlWriter(self.TABLE_NAME)
        insert_sql = writer.insert_statement(insert_columns)

        throughput_aliases = self._collect_throughput_headers(headers)
        values: List[List[Any]] = []
        for row in rows:
            row_values: List[Any] = [
                test_report_id,
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


def _resolve_wifi_product_details(fpga_section: Any) -> Dict[str, Any]:
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
    details: Dict[str, Any] = {
        "customer": None,
        "project_type": None,
        "nickname": None,
        "project_name": None,
        "project_id": None,
        "main_chip": None,
        "wifi_module": None,
        "interface": None,
        "ecosystem": None,
    }

    if not isinstance(fpga_section, Mapping):
        raise ValueError("project section must be a mapping containing customer/project_type/project.")

    customer = str(fpga_section.get("customer") or "").strip()
    project_type = str(fpga_section.get("project_type") or "").strip()
    nickname = str(fpga_section.get("project") or "").strip()
    if not customer or not project_type or not nickname:
        raise ValueError("project section must include non-empty customer/project_type/project.")
    if project_type not in PROJECT_TYPES:
        raise ValueError(f"Unsupported project_type={project_type!r}; allowed={list(PROJECT_TYPES)!r}")

    details["customer"] = customer
    details["project_type"] = project_type
    details["nickname"] = nickname
    details["main_chip"] = _normalize_upper_token(fpga_section.get("soc") or fpga_section.get("main_chip"))
    details["wifi_module"] = _normalize_upper_token(fpga_section.get("wifi_module") or fpga_section.get("series"))
    details["interface"] = _normalize_upper_token(fpga_section.get("interface"))
    details["ecosystem"] = _normalize_str_token(fpga_section.get("ecosystem"))

    try:
        info = WIFI_PRODUCT_PROJECT_MAP[project_type][customer][nickname]
    except KeyError as exc:
        raise KeyError(
            f"Unknown mapping for project_type={project_type!r}, customer={customer!r}, project={nickname!r}"
        ) from exc

    if info:
        details["project_id"] = str(info.get("ProjectID") or "").strip() or None
        details["project_name"] = str(info.get("ProjectName") or "").strip() or None
        expected_chip = _normalize_upper_token(info.get("main_chip"))
        expected_wifi = _normalize_upper_token(info.get("wifi_module"))
        expected_if = _normalize_upper_token(info.get("interface"))
        expected_ecosystem = _normalize_str_token(info.get("ecosystem"))

        if details["main_chip"] and expected_chip and details["main_chip"] != expected_chip:
            raise ValueError(f"project.soc mismatch: {details['main_chip']!r} != {expected_chip!r}")
        if details["wifi_module"] and expected_wifi and details["wifi_module"] != expected_wifi:
            raise ValueError(f"project.wifi_module mismatch: {details['wifi_module']!r} != {expected_wifi!r}")
        if details["interface"] and expected_if and details["interface"] != expected_if:
            raise ValueError(f"project.interface mismatch: {details['interface']!r} != {expected_if!r}")
        if details["ecosystem"] and expected_ecosystem and details["ecosystem"] != expected_ecosystem:
            raise ValueError(f"project.ecosystem mismatch: {details['ecosystem']!r} != {expected_ecosystem!r}")

        details["main_chip"] = expected_chip
        details["wifi_module"] = expected_wifi
        details["interface"] = expected_if
        details["ecosystem"] = expected_ecosystem

    return details


def _build_project_payload(config: Mapping[str, Any]) -> Dict[str, Any]:
    project_section = config.get("project")
    if not isinstance(project_section, Mapping):
        project_section = config.get("fpga")
    global _DBTRACE_PROJECT_ONCE
    try:
        _DBTRACE_PROJECT_ONCE
    except NameError:
        _DBTRACE_PROJECT_ONCE = False  # type: ignore[assignment]

    if not _DBTRACE_PROJECT_ONCE:
        _DBTRACE_PROJECT_ONCE = True  # type: ignore[assignment]
        print("[DBTRACE_PROJECT] Paths.CONFIG_DIR=", Paths.CONFIG_DIR, flush=True)
        print("[DBTRACE_PROJECT] config.project=", project_section, flush=True)
        logging.info("[DBTRACE_PROJECT] Paths.CONFIG_DIR=%s", Paths.CONFIG_DIR)
        logging.info("[DBTRACE_PROJECT] config.project=%s", project_section)
    wifi_details = _resolve_wifi_product_details(project_section)
    out = {
        "customer": wifi_details.get("customer"),
        "project_type": wifi_details.get("project_type"),
        "nickname": wifi_details.get("nickname"),
        "project_name": wifi_details.get("project_name"),
        "project_id": wifi_details.get("project_id"),
        "soc": wifi_details.get("main_chip"),
        "wifi_module": wifi_details.get("wifi_module"),
        "odm": wifi_details.get("odm") or wifi_details.get("ODM") or None,
        "interface": wifi_details.get("interface"),
        "ecosystem": wifi_details.get("ecosystem"),
    }
    if _DBTRACE_PROJECT_ONCE:
        print("[DBTRACE_PROJECT] resolved_wifi_details=", wifi_details, flush=True)
        print("[DBTRACE_PROJECT] project_payload=", out, flush=True)
        logging.info("[DBTRACE_PROJECT] resolved_wifi_details=%s", wifi_details)
        logging.info("[DBTRACE_PROJECT] project_payload=%s", out)
    return out


_PROJECT_COLUMNS_CACHE: Optional[set[str]] = None


def _get_project_columns(client: MySqlClient) -> set[str]:
    global _PROJECT_COLUMNS_CACHE
    if _PROJECT_COLUMNS_CACHE is None:
        try:
            rows = client.query_all("SHOW COLUMNS FROM `project`")
            _PROJECT_COLUMNS_CACHE = {str(r.get("Field") or "") for r in rows if isinstance(r, dict)}
        except Exception:
            _PROJECT_COLUMNS_CACHE = set()
    return set(_PROJECT_COLUMNS_CACHE or set())


def _project_column_names(columns: set[str], *, include_project_id: bool) -> list[str]:
    names: list[str] = []
    if "customer" in columns:
        names.append("customer")
    if "brand" in columns:
        names.append("brand")
    if "project_type" in columns:
        names.append("project_type")
    if "product_line" in columns:
        names.append("product_line")
    for name in ("nickname", "project_name"):
        if name in columns:
            names.append(name)
    if include_project_id and "project_id" in columns:
        names.append("project_id")
    if "soc" in columns:
        names.append("soc")
    if "main_chip" in columns:
        names.append("main_chip")
    for name in ("wifi_module", "odm", "interface", "ecosystem"):
        if name in columns:
            names.append(name)
    return names


def _project_column_value(project_payload: Mapping[str, Any], column_name: str) -> Any:
    if column_name in {"customer", "brand"}:
        return project_payload.get("customer")
    if column_name in {"project_type", "product_line"}:
        return project_payload.get("project_type")
    if column_name in {"soc", "main_chip"}:
        return project_payload.get("soc")
    return project_payload.get(column_name)


def ensure_project(client: MySqlClient, project_payload: Mapping[str, Any]) -> int:
    columns = _get_project_columns(client)

    project_id = str(project_payload.get("project_id") or "").strip()

    if project_id:
        print("[DBTRACE_PROJECT] ensure_project lookup project_id=", project_id, flush=True)
        logging.info("[DBTRACE_PROJECT] ensure_project lookup project_id=%s", project_id)
        existing = client.query_one(
            "SELECT `id` FROM `project` WHERE `project_id`=%s ORDER BY `id` DESC LIMIT 1",
            (project_id,),
        )
        if existing and existing.get("id"):
            existing_id = int(existing["id"])
            print("[DBTRACE_PROJECT] ensure_project hit id=", existing_id, flush=True)
            logging.info("[DBTRACE_PROJECT] ensure_project hit id=%s", existing_id)
            update_columns = _project_column_names(columns, include_project_id=False)
            set_fields = [f"`{column}`=%s" for column in update_columns]
            values = [_project_column_value(project_payload, column) for column in update_columns]
            values.append(existing_id)
            client.execute(
                f"UPDATE `project` SET {', '.join(set_fields)} WHERE `id`=%s",
                tuple(values),
            )
            return existing_id

    insert_columns = _project_column_names(columns, include_project_id=True)
    insert_values = [_project_column_value(project_payload, column) for column in insert_columns]

    placeholder = ", ".join(["%s"] * len(insert_columns))
    insert_sql = (
        f"INSERT INTO `project` ({', '.join(f'`{column}`' for column in insert_columns)}) "
        f"VALUES ({placeholder}) "
        "ON DUPLICATE KEY UPDATE "
        "`id`=LAST_INSERT_ID(`id`), "
        + ", ".join(f"`{column}`=VALUES(`{column}`)" for column in insert_columns)
    )
    return client.insert(
        insert_sql,
        tuple(insert_values),
    )


_PROJECT_CATALOG_SYNCED = False
_ROUTER_CATALOG_SYNCED = False
_LAB_CATALOG_SYNCED = False


def _load_cached_tester() -> Optional[str]:
    path = Path(Paths.CONFIG_DIR) / "auth_state.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logging.debug("Failed to read auth state from %s", path, exc_info=True)
        return None
    if not isinstance(data, Mapping):
        return None
    username = str(data.get("username") or "").strip()
    authenticated = bool(data.get("authenticated", False))
    if not username or not authenticated:
        return None
    return username


def _load_router_catalog() -> list[dict[str, Any]]:
    path = Path(Paths.CONFIG_DIR) / "compatibility_router.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def sync_router_catalog(client: MySqlClient) -> None:
    global _ROUTER_CATALOG_SYNCED
    if _ROUTER_CATALOG_SYNCED:
        return

    entries = _load_router_catalog()
    insert_sql = (
        "INSERT INTO `router` (`ip`, `port`, `brand`, `model`) "
        "VALUES (%s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "`brand`=VALUES(`brand`), "
        "`model`=VALUES(`model`)"
    )
    rows: list[tuple[Any, ...]] = []
    expected_keys: set[tuple[str, int]] = set()
    for entry in entries:
        ip = str(entry.get("ip") or "").strip()
        try:
            port = int(str(entry.get("port") or "").strip())
        except Exception:
            continue
        if not ip or port <= 0:
            continue
        brand = str(entry.get("brand") or "").strip()
        model = str(entry.get("model") or "").strip()
        expected_keys.add((ip, port))
        rows.append((ip, port, brand, model))

    if rows:
        logging.info("Router catalog sync: upserting %d rows", len(rows))
        client.executemany(insert_sql, rows)

    _ROUTER_CATALOG_SYNCED = True


def sync_lab_catalog(client: MySqlClient) -> None:
    global _LAB_CATALOG_SYNCED
    if _LAB_CATALOG_SYNCED:
        return

    insert_sql = (
        "INSERT INTO `lab` (`lab_name`, `turntable`, `attenuator`) "
        "VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "`turntable`=VALUES(`turntable`), "
        "`attenuator`=VALUES(`attenuator`)"
    )

    rows: list[tuple[Any, ...]] = []
    for lab_name, info in LAB_CATALOG.items():
        capabilities = sorted({str(x) for x in (info.get("capabilities") or [])})
        invalid_capabilities = sorted(
            capability for capability in capabilities if capability not in LAB_CAPABILITY_CHOICES
        )
        if invalid_capabilities:
            raise ValueError(
                f"Unsupported lab capabilities for {lab_name!r}: {invalid_capabilities!r}; "
                f"allowed={list(LAB_CAPABILITY_CHOICES)!r}"
            )
        equipment = info.get("equipment") if isinstance(info.get("equipment"), Mapping) else {}
        turntable_model = equipment.get("turntable_model") if equipment else None
        rf_model = equipment.get("rf_model") if equipment else None
        rows.append(
            (
                str(lab_name),
                None if turntable_model is None else str(turntable_model),
                None if rf_model is None else str(rf_model),
            )
        )

    if rows:
        logging.info("Lab catalog sync: upserting %d rows", len(rows))
        client.executemany(insert_sql, rows)
        lab_rows = client.query_all("SELECT `id`, `lab_name` FROM `lab`")
        lab_ids = {
            str(row.get("lab_name") or ""): int(row["id"])
            for row in lab_rows
            if isinstance(row, dict) and row.get("id") is not None
        }
        managed_lab_ids = [lab_ids[name] for name in LAB_CATALOG.keys() if name in lab_ids]
        if managed_lab_ids:
            placeholders = ", ".join(["%s"] * len(managed_lab_ids))
            client.execute(
                f"DELETE FROM `lab_capability` WHERE `lab_id` IN ({placeholders})",
                tuple(managed_lab_ids),
            )
            capability_rows: list[tuple[int, str]] = []
            for lab_name, info in LAB_CATALOG.items():
                lab_id = lab_ids.get(str(lab_name))
                if lab_id is None:
                    continue
                for capability in sorted({str(x) for x in (info.get('capabilities') or [])}):
                    capability_rows.append((lab_id, capability))
            if capability_rows:
                client.executemany(
                    "INSERT INTO `lab_capability` (`lab_id`, `capability`) VALUES (%s, %s)",
                    capability_rows,
                )

    _LAB_CATALOG_SYNCED = True


def sync_catalogs(client: MySqlClient) -> None:
    sync_project_catalog(client)
    sync_router_catalog(client)
    sync_lab_catalog(client)


def prepare_database(client: MySqlClient, *, reset_schema: bool = False) -> None:
    from .schema import ensure_report_tables, reset_report_schema

    if reset_schema:
        reset_report_schema(client)
    else:
        ensure_report_tables(client)
    sync_catalogs(client)


def sync_project_catalog(client: MySqlClient) -> None:
    global _PROJECT_CATALOG_SYNCED
    if _PROJECT_CATALOG_SYNCED:
        try:
            row = client.query_one("SELECT COUNT(1) AS c FROM `project`")
            count = int((row or {}).get("c") or 0)
        except Exception:
            count = 1
        if count > 0:
            return
    print("[PROJECT_SYNC] start")
    columns = _get_project_columns(client)
    insert_columns = _project_column_names(columns, include_project_id=True)
    placeholders = ", ".join(["%s"] * len(insert_columns))
    insert_sql = (
        "INSERT INTO `project` "
        f"({', '.join(f'`{column}`' for column in insert_columns)}) "
        f"VALUES ({placeholders}) "
        "ON DUPLICATE KEY UPDATE "
        + ", ".join(f"`{column}`=VALUES(`{column}`)" for column in insert_columns)
    )
    rows = []
    update_rows: list[tuple[Any, ...]] = []
    for project_type, customer_map in WIFI_PRODUCT_PROJECT_MAP.items():
        for customer_name, projects in customer_map.items():
            for nickname, info in projects.items():
                project_id = str(info.get("ProjectID") or "").strip()
                project_name = str(info.get("ProjectName") or "").strip() or None
                project_payload = {
                    "customer": customer_name,
                    "project_type": project_type,
                    "nickname": nickname,
                    "project_name": project_name,
                    "project_id": project_id or None,
                    "soc": info.get("main_chip"),
                    "wifi_module": info.get("wifi_module"),
                    "odm": info.get("ODM") or None,
                    "interface": info.get("interface"),
                    "ecosystem": info.get("ecosystem"),
                }
                if nickname in {"Latte829", "Vodka424", "Espresso115"} or not project_id:
                    print(
                        "[PROJECT_SYNC] map_row",
                        "project_type=",
                        project_type,
                        "customer=",
                        customer_name,
                        "nickname=",
                        nickname,
                        "ProjectID=",
                        project_id or "(empty)",
                        "ProjectName=",
                        project_name or "(empty)",
                    )
                rows.append(
                    tuple(_project_column_value(project_payload, column) for column in insert_columns)
                )
                if project_payload.get("project_id"):
                    update_rows.append(
                        (
                            project_payload.get("project_id"),
                            project_payload.get("project_name"),
                            project_payload.get("customer"),
                            project_payload.get("project_type"),
                            project_payload.get("nickname"),
                        )
                    )
    if rows:
        missing_id = len(rows) - len(update_rows)
        print("[PROJECT_SYNC] rows=", len(rows), "missing_project_id=", missing_id)
        logging.info("Project catalog sync: upserting %d rows", len(rows))
        client.executemany(insert_sql, rows)
        customer_lookup_column = "customer" if "customer" in columns else "brand"
        project_type_lookup_column = "project_type" if "project_type" in columns else "product_line"
        if update_rows and customer_lookup_column and project_type_lookup_column and "nickname" in columns:
            client.executemany(
                f"UPDATE `project` SET `project_id`=%s, `project_name`=%s "
                f"WHERE `{customer_lookup_column}`=%s AND `{project_type_lookup_column}`=%s AND `nickname`=%s",
                update_rows,
            )
        try:
            sample = client.query_all(
                "SELECT `id`, `customer`, `project_type`, `nickname`, `project_name`, `project_id` "
                "FROM `project` WHERE `nickname` IN (%s, %s, %s) ORDER BY `id`",
                ("Vodka424", "Latte829", "Espresso115"),
            )
        except Exception as exc:
            sample = [{"error": str(exc)}]
        print("[PROJECT_SYNC] db_sample=", sample)
    print("[PROJECT_SYNC] done")
    _PROJECT_CATALOG_SYNCED = True


def ensure_test_report(
    client: MySqlClient,
    *,
    project_id: int,
    lab_id: Optional[int] = None,
    report_name: str,
    case_path: Optional[str],
    is_golden: bool = False,
    report_type: Optional[str] = None,
    golden_group: Optional[str] = None,
    notes: Optional[str] = None,
    tester: Optional[str] = None,
    csv_name: Optional[str] = None,
    csv_path: Optional[str] = None,
) -> int:
    if tester is None:
        tester = _load_cached_tester()

    insert_sql = (
        "INSERT INTO `test_report` "
        "(`project_id`, `lab_id`, `report_name`, `case_path`, `is_golden`, `report_type`, `golden_group`, `notes`, `tester`, "
        "`csv_name`, `csv_path`) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "`id`=LAST_INSERT_ID(`id`), "
        "`lab_id`=VALUES(`lab_id`), "
        "`case_path`=VALUES(`case_path`), "
        "`is_golden`=VALUES(`is_golden`), "
        "`report_type`=VALUES(`report_type`), "
        "`golden_group`=VALUES(`golden_group`), "
        "`notes`=VALUES(`notes`), "
        "`tester`=VALUES(`tester`), "
        "`csv_name`=VALUES(`csv_name`), "
        "`csv_path`=VALUES(`csv_path`)"
    )
    return client.insert(
        insert_sql,
        (
            project_id,
            lab_id,
            report_name,
            case_path,
            1 if is_golden else 0,
            report_type,
            golden_group,
            notes,
            tester,
            csv_name,
            csv_path,
        ),
    )


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
    def _normalize_run_source(value: str) -> str:
        token = str(value or "").strip()
        upper = token.upper()
        if not upper:
            return "auto"
        if upper in {"FRAMEWORK", "LOCAL", "AUTO", "AUTO_TEST"}:
            return "auto"
        if upper in {"IMPORT"}:
            return "import"
        if upper in {"MANUAL", "MANUAL_TEST"}:
            return "manual"
        return token.lower()

    normalized_source = _normalize_run_source(run_source)
    print("[DBTRACE_PROJECT] register_execution payload=", dict(project_payload), flush=True)
    print(
        "[DBTRACE_PROJECT] register_execution report_name=",
        report_name,
        "execution_type=",
        execution_type,
        flush=True,
    )
    logging.info("[DBTRACE_PROJECT] register_execution payload=%s", dict(project_payload))
    logging.info("[DBTRACE_PROJECT] register_execution report_name=%s execution_type=%s", report_name, execution_type)
    logging.info(
        "[DBTRACE_EXEC] register_execution start csv=%s source=%s type=%s",
        csv_name,
        normalized_source,
        execution_type,
    )
    report_type = _require_test_report_type(execution_type)
    run_type = _require_run_type(RUN_TYPE_WIFI_SMARTTEST)
    lab_id: Optional[int] = None
    lab_name = execution_payload.get("lab_name")
    if isinstance(lab_name, str) and lab_name.strip():
        rows = client.query_all("SELECT id FROM `lab` WHERE `lab_name`=%s LIMIT 1", (lab_name.strip(),))
        if rows:
            lab_id = int(rows[0]["id"])
    project_id = ensure_project(client, project_payload)
    row = client.query_one(
        "SELECT `id`, `customer`, `project_type`, `nickname`, `project_name`, `project_id` "
        "FROM `project` WHERE `id`=%s",
        (int(project_id),),
    )
    print("[DBTRACE_PROJECT] ensured_project=", row, flush=True)
    logging.info("[DBTRACE_PROJECT] ensured_project=%s", row)
    test_report_id = ensure_test_report(
        client,
        project_id=project_id,
        lab_id=lab_id,
        report_name=report_name,
        case_path=case_path,
        is_golden=False,
        report_type=report_type,
        notes=None,
        csv_name=csv_name,
        csv_path=csv_path,
    )
    logging.info(
        "[DBTRACE_EXEC] project_id=%s test_report_id=%s case_path=%s",
        project_id,
        test_report_id,
        case_path,
    )

    dut_payload = {
        "test_report_id": int(test_report_id),
        "sn": execution_payload.get("sn") or execution_payload.get("serial_number"),
        "mac_address": execution_payload.get("mac_address"),
        "adb_device": execution_payload.get("adb_device"),
        "ip": execution_payload.get("ip") or execution_payload.get("telnet_ip"),
        "software_version": execution_payload.get("software_version"),
        "driver_version": execution_payload.get("driver_version"),
        "android_version": execution_payload.get("android_version"),
        "kernel_version": execution_payload.get("kernel_version"),
        "os": execution_payload.get("os"),
        "hw_phase": execution_payload.get("hw_phase"),
        "wifi_module_sn": execution_payload.get("wifi_module_sn"),
        "antenna": execution_payload.get("antenna"),
    }
    client.insert(
        "INSERT INTO `dut` "
        "(`test_report_id`, `sn`, `mac_address`, `adb_device`, `ip`, "
        "`software_version`, `driver_version`, `android_version`, `kernel_version`, `os`, `hw_phase`, `wifi_module_sn`, `antenna`) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "`id`=LAST_INSERT_ID(`id`), "
        "`test_report_id`=VALUES(`test_report_id`), "
        "`sn`=VALUES(`sn`), "
        "`mac_address`=VALUES(`mac_address`), "
        "`adb_device`=VALUES(`adb_device`), "
        "`ip`=VALUES(`ip`), "
        "`software_version`=VALUES(`software_version`), "
        "`driver_version`=VALUES(`driver_version`), "
        "`android_version`=VALUES(`android_version`), "
        "`kernel_version`=VALUES(`kernel_version`), "
        "`os`=VALUES(`os`), "
        "`hw_phase`=VALUES(`hw_phase`), "
        "`wifi_module_sn`=VALUES(`wifi_module_sn`), "
        "`antenna`=VALUES(`antenna`)",
        (
            dut_payload.get("test_report_id"),
            dut_payload.get("sn"),
            dut_payload.get("mac_address"),
            dut_payload.get("adb_device"),
            dut_payload.get("ip"),
            dut_payload.get("software_version"),
            dut_payload.get("driver_version"),
            dut_payload.get("android_version"),
            dut_payload.get("kernel_version"),
            dut_payload.get("os"),
            dut_payload.get("hw_phase"),
            dut_payload.get("wifi_module_sn"),
            dut_payload.get("antenna"),
        ),
    )
    logging.info("[DBTRACE_EXEC] dut_upserted hw_phase=%s", dut_payload.get("hw_phase"))
    if lab_id is not None:
        lab_environment_payload = {
            "lab_id": int(lab_id),
            "ap_name": execution_payload.get("ap_name") or execution_payload.get("router_name"),
            "ap_address": execution_payload.get("ap_address") or execution_payload.get("router_address"),
            "distance": execution_payload.get("distance"),
            "ap_region": execution_payload.get("ap_region"),
            "connect_type": execution_payload.get("connect_type"),
            "coex_mode": execution_payload.get("coex_mode"),
            "bt_remote": execution_payload.get("bt_remote"),
            "bt_device": execution_payload.get("bt_device"),
            "bt_type": execution_payload.get("bt_type"),
        }
        client.insert(
            "INSERT INTO `lab_environment` "
            "(`lab_id`, `ap_name`, `ap_address`, `distance`, `ap_region`, `connect_type`, `coex_mode`, `bt_remote`, `bt_device`, `bt_type`) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "`id`=LAST_INSERT_ID(`id`), "
            "`ap_name`=VALUES(`ap_name`), "
            "`ap_address`=VALUES(`ap_address`), "
            "`distance`=VALUES(`distance`), "
            "`ap_region`=VALUES(`ap_region`), "
            "`connect_type`=VALUES(`connect_type`), "
            "`coex_mode`=VALUES(`coex_mode`), "
            "`bt_remote`=VALUES(`bt_remote`), "
            "`bt_device`=VALUES(`bt_device`), "
            "`bt_type`=VALUES(`bt_type`)",
            (
                lab_environment_payload.get("lab_id"),
                lab_environment_payload.get("ap_name"),
                lab_environment_payload.get("ap_address"),
                lab_environment_payload.get("distance"),
                lab_environment_payload.get("ap_region"),
                lab_environment_payload.get("connect_type"),
                lab_environment_payload.get("coex_mode"),
                lab_environment_payload.get("bt_remote"),
                lab_environment_payload.get("bt_device"),
                lab_environment_payload.get("bt_type"),
            ),
        )

    insert_sql = (
        "INSERT INTO `execution` "
        "(`test_report_id`, `run_type`, `run_source`, `duration_seconds`) "
        "VALUES (%s, %s, %s, %s)"
    )
    execution_id = client.insert(
        insert_sql,
        (
            test_report_id,
            run_type,
            normalized_source,
            int(duration_seconds) if duration_seconds is not None else None,
        ),
    )
    logging.info(
        "[DBTRACE_EXEC] execution_id=%s lab_id=%s duration=%s",
        execution_id,
        lab_id,
        duration_seconds,
    )
    return execution_id


def _extract_serial_number(config: Mapping[str, Any]) -> Optional[str]:
    hardware_section = _extract_first(config, "hardware_info", "hardware")
    hardware = hardware_section if isinstance(hardware_section, Mapping) else {}
    return _normalize_str_token(
        _extract_first(hardware, "serial_number", "serial", "sn", "serialnumber")
        or config.get("serial_number")
        or config.get("serial")
    )


def _build_execution_device_payload(config: Mapping[str, Any]) -> Dict[str, Any]:
    software_section = config.get("software_info")
    software = software_section if isinstance(software_section, Mapping) else {}

    system_section = config.get("android_system")
    if not isinstance(system_section, Mapping):
        system_section = config.get("system")
    if not isinstance(system_section, Mapping):
        system_section = config.get("android")
    system_info = system_section if isinstance(system_section, Mapping) else {}

    connect_section = config.get("dut")
    if not isinstance(connect_section, Mapping):
        connect_section = config.get("connect_type")
    connect = connect_section if isinstance(connect_section, Mapping) else {}

    project_section = config.get("project")
    project = project_section if isinstance(project_section, Mapping) else {}
    fpga_section = project.get("fpga") if isinstance(project.get("fpga"), Mapping) else None
    project_info = fpga_section if isinstance(fpga_section, Mapping) else project

    adb_device: Optional[str] = None
    dut_ip: Optional[str] = None

    control_type = _normalize_lower_token(_normalize_str_token(connect.get("type")))
    if control_type == "android":
        adb_device = _normalize_str_token(_extract_first(connect, "Android", "device"))
    elif control_type == "linux":
        dut_ip = _normalize_str_token(_extract_first(connect, "Linux", "ip"))

    hw_phase = _normalize_str_token(connect.get("hw_phase"))
    if hw_phase and hw_phase not in HW_PHASE_CHOICES:
        raise ValueError(f"Unsupported dut.hw_phase={hw_phase!r}; allowed={list(HW_PHASE_CHOICES)!r}")
    dut_os = _normalize_str_token(connect.get("os"))
    if dut_os and dut_os not in DUT_OS_CHOICES:
        raise ValueError(f"Unsupported dut.os={dut_os!r}; allowed={list(DUT_OS_CHOICES)!r}")

    sn = _extract_serial_number(config)
    wifi_module_sn = _normalize_str_token(_extract_first(connect, "wifi_module_sn", "wifi_sn", "module_sn"))
    antenna = _normalize_str_token(_extract_first(connect, "antenna"))

    return {
        "sn": sn,
        "serial_number": sn,
        "software_version": software.get("software_version"),
        "driver_version": software.get("driver_version"),
        "android_version": system_info.get("version"),
        "kernel_version": system_info.get("kernel_version"),
        "os": dut_os,
        "mac_address": _normalize_str_token(connect.get("mac_address")),
        "adb_device": adb_device,
        "ip": dut_ip,
        "telnet_ip": dut_ip,
        "odm": _normalize_str_token(project_info.get("odm")),
        "wifi_module_sn": wifi_module_sn,
        "antenna": antenna,
        "hw_phase": hw_phase,
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
        ap_name = None
        ap_address = None
    else:
        ap_name = _normalize_str_token(router.get("name"))
        ap_address = _normalize_str_token(router.get("address"))

    lab_env_section = _extract_first(config, "lab_environment", "lab_enviroment")
    lab_env = lab_env_section if isinstance(lab_env_section, Mapping) else {}
    distance = _normalize_str_token(lab_env.get("distance"))
    ap_region = _normalize_str_token(lab_env.get("ap_region"))
    connect_type = _normalize_str_token(lab_env.get("connect_type"))
    coex_mode = _normalize_str_token(lab_env.get("coex_mode"))
    bt_remote = _normalize_str_token(lab_env.get("bt_remote"))
    bt_device = _normalize_str_token(lab_env.get("bt_device"))
    bt_type = _normalize_str_token(lab_env.get("bt_type"))
    explicit_ap_name = _normalize_str_token(lab_env.get("ap_name"))
    if explicit_ap_name:
        ap_name = explicit_ap_name
    if ap_name and ap_name not in AP_MODEL_CHOICES:
        raise ValueError(
            f"Unsupported lab_enviroment.ap_name={ap_name!r}; "
            f"allowed={list(AP_MODEL_CHOICES)!r}"
        )
    if ap_region and ap_region not in AP_REGION_CHOICES:
        raise ValueError(
            f"Unsupported lab_enviroment.ap_region={ap_region!r}; "
            f"allowed={list(AP_REGION_CHOICES)!r}"
        )
    if connect_type and connect_type not in LAB_ENV_CONNECT_TYPE_CHOICES:
        raise ValueError(
            f"Unsupported lab_enviroment.connect_type={connect_type!r}; "
            f"allowed={list(LAB_ENV_CONNECT_TYPE_CHOICES)!r}"
        )
    if coex_mode and coex_mode not in LAB_ENV_COEX_MODE_CHOICES:
        raise ValueError(
            f"Unsupported lab_enviroment.coex_mode={coex_mode!r}; "
            f"allowed={list(LAB_ENV_COEX_MODE_CHOICES)!r}"
        )
    if bt_remote and bt_remote not in BT_REMOTE_CHOICES:
        raise ValueError(f"Unsupported lab_enviroment.bt_remote={bt_remote!r}; allowed={list(BT_REMOTE_CHOICES)!r}")
    if bt_device and bt_device not in BT_DEVICE_CHOICES:
        raise ValueError(f"Unsupported lab_enviroment.bt_device={bt_device!r}; allowed={list(BT_DEVICE_CHOICES)!r}")
    if bt_type and bt_type not in BT_TYPE_CHOICES:
        raise ValueError(f"Unsupported lab_enviroment.bt_type={bt_type!r}; allowed={list(BT_TYPE_CHOICES)!r}")
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

    if lab_name and lab_name not in LAB_NAME_CHOICES:
        raise ValueError(f"Unsupported lab.lab_name={lab_name!r}; allowed={list(LAB_NAME_CHOICES)!r}")

    return {
        "ap_name": ap_name,
        "ap_address": ap_address,
        "router_name": ap_name,
        "router_address": ap_address,
        "attenuator": rf_model,
        "rf_model": rf_model,
        "turntable": corner_model,
        "corner_model": corner_model,
        "distance": distance,
        "ap_region": ap_region,
        "connect_type": connect_type,
        "coex_mode": coex_mode,
        "bt_remote": bt_remote,
        "bt_device": bt_device,
        "bt_type": bt_type,
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
        prepare_database(client)
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
            base_dir = get_config_base()
            basic_path = base_dir / BASIC_CONFIG_FILENAME
            print("[DBTRACE_SYNC] config_base=", str(base_dir), "basic_yaml=", str(basic_path), flush=True)
            try:
                import yaml as _yaml

                raw_basic = _yaml.safe_load(basic_path.read_text(encoding="utf-8")) or {}
                raw_project = raw_basic.get("project") if isinstance(raw_basic, dict) else None
            except Exception as exc:
                raw_project = {"error": str(exc)}
            print("[DBTRACE_SYNC] raw_basic.project=", raw_project, flush=True)
            active_config = load_config(refresh=True)
        except Exception:
            logging.debug(
                "sync_test_result_to_db: failed to load configuration for persistence",
                exc_info=True,
            )
            active_config = None

    if active_config:
        print("[DBTRACE_SYNC] active_config.project=", active_config.get("project"), flush=True)
        project_payload = _build_project_payload(active_config)
        execution_payload = _build_execution_payload(active_config)
        resolved_case_path = case_path or _resolve_case_path(active_config)
    else:
        logging.debug("sync_test_result_to_db: no configuration available for database sync.")
        project_payload = {}
        execution_payload = {}
        resolved_case_path = case_path

    print("[DBTRACE_SYNC] project_payload=", dict(project_payload), flush=True)
    print("[DBTRACE_SYNC] case_path=", resolved_case_path, "log_file=", log_file, "data_type=", data_type, flush=True)

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

    normalized_data_type = _require_test_report_type(data_type if isinstance(data_type, str) else None)
    normalized_execution_type = normalized_data_type
    normalized_performance_type = normalized_data_type
    normalized_source = (run_source or "local").strip() or "local"
    normalized_source = normalized_source.upper()[:32]

    if normalized_data_type in {TEST_REPORT_RVR, TEST_REPORT_RVO}:
        try:
            from src.tools.performance import generate_rvr_charts
        except Exception:
            logging.exception(
                "sync_test_result_to_db: unable to import chart generator for %s", normalized_data_type
            )
        else:
            try:
                charts_subdir = 'rvo_charts' if normalized_data_type == TEST_REPORT_RVO else 'rvr_charts'
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
            prepare_database(client)
            manager = PerformanceTableManager(client)
            manager.ensure_schema_initialized()
            affected = manager.replace_with_csv(
                csv_name=file_path.name,
                csv_path=str(file_path),
                headers=headers,
                rows=rows,
                data_type=normalized_performance_type,
                execution_type=normalized_execution_type,
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
    then bulk inserts rows into `compatibility` linked by `test_report_id`
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
        prepare_database(client)

        with open(router_json, "r", encoding="utf-8") as handle:
            router_entries = json.load(handle) or []

        upsert_sql = (
            "INSERT INTO `router` (`ip`, `port`, `brand`, `model`) "
            "VALUES (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "`brand`=VALUES(`brand`), `model`=VALUES(`model`)"
        )
        router_rows = []
        for entry in router_entries:
            ip = str(entry.get("ip") or "").strip()
            port = int(str(entry.get("port") or "0").strip() or 0)
            if not ip or port <= 0:
                continue
            brand = str(entry.get("brand") or "").strip()
            model = str(entry.get("model") or "").strip()
            router_rows.append((ip, port, brand, model))
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
            execution_type=TEST_REPORT_COMPATIBILITY,
            execution_payload=execution_payload,
            csv_name=Path(csv_file).name,
            csv_path=str(Path(csv_file).resolve()),
            run_source=normalized_source,
            duration_seconds=duration_seconds,
        )
        test_report_row = client.query_one(
            "SELECT `test_report_id` FROM `execution` WHERE `id`=%s LIMIT 1",
            (execution_id,),
        )
        test_report_id = int((test_report_row or {}).get("test_report_id") or 0)

        with open(csv_file, "r", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            rows = list(reader)

        if not rows or len(rows) < 2:
            return 0

        data_rows = rows[1:]
        insert_cols = [
            "test_report_id",
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
                    test_report_id,
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

    active_config = config if isinstance(config, dict) else None
    if active_config is None:
        active_config = load_config(refresh=True) or {}

    print(
        "[DBTRACE_SYNC] sync_file_to_db type=",
        data_type,
        "log=",
        file_path,
        "config_project=",
        active_config.get("project") if isinstance(active_config, dict) else None,
        flush=True,
    )
    logging.info(
        "[DBTRACE_SYNC] sync_file_to_db type=%s log=%s config_project=%s",
        data_type,
        file_path,
        (active_config.get("project") if isinstance(active_config, dict) else None),
    )

    return sync_test_result_to_db(
        active_config,
        log_file=file_path,
        data_type=data_type,
        case_path=case_path,
        run_source=run_source,
        duration_seconds=duration_seconds,
    )
