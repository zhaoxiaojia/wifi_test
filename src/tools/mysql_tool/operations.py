from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Mapping, Callable

from .client import MySqlClient
from .schema import (
    PERFORMANCE_COLUMN_RENAMES,
    PERFORMANCE_STATIC_COLUMNS,
    ensure_report_tables,
    read_csv_rows,
)
from src.util.constants import WIFI_PRODUCT_PROJECT_MAP

__all__ = [
    "PerformanceTableManager",
    "sync_configuration",
    "sync_test_result_to_db",
    "sync_file_to_db",
]


ColumnNormalizer = Callable[[Any], Any]


@dataclass(frozen=True)
class _StaticColumn:
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
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    # Allow direct matches first
    if lowered in _ALLOWED_BANDS:
        return lowered
    # Remove unit suffixes like "ghz" or "g"
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
    # Handle values like 802.11ax, 11AX, etc.
    match = re.search(r"11[a-z]{1,2}", text)
    if match:
        candidate = match.group(0)
        if candidate in _ALLOWED_STANDARDS:
            return candidate
    return None


def _normalize_angle_token(value: Any) -> Optional[float]:
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
    """Manage the performance table with a fixed schema and cumulative writes."""

    TABLE_NAME = "performance"
    REPORT_TABLE_NAME = "test_report"

    _BASE_COLUMNS: Sequence[tuple[str, str]] = (
        ("test_report_id", "INT NOT NULL"),
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
        self._client = client

    @staticmethod
    def _classify_value(value: Any) -> tuple[str, Any]:
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
        return {
            column["Field"]: column
            for column in self._client.query_all(f"SHOW FULL COLUMNS FROM `{self.TABLE_NAME}`")
        }

    def _ensure_static_columns(self) -> None:
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
        samples: List[float] = []
        for value in values:
            samples.extend(cls._parse_throughput_value(value))
        if not samples:
            return None
        return sum(samples) / len(samples)

    @staticmethod
    def _format_column_definition(column: _StaticColumn) -> str:
        comment = column.original.replace("'", "''")
        return f"{column.sql_type} NULL DEFAULT NULL COMMENT '{comment}'"

    def _resolve_execution_id(self, case_path: Optional[str]) -> Optional[int]:
        if not case_path:
            return None
        try:
            row = self._client.query_one(
                "SELECT id FROM `execution` WHERE case_path = %s ORDER BY id DESC LIMIT 1",
                (case_path,),
            )
        except Exception:
            logging.debug(
                "Failed to resolve execution id via case_path=%s",
                case_path,
                exc_info=True,
            )
            return None
        if row and "id" in row and row["id"] is not None:
            return int(row["id"])
        return None

    def _register_test_report(
        self,
        *,
        csv_name: str,
        csv_path: str,
        data_type: Optional[str],
        case_path: Optional[str],
        execution_id: Optional[int],
        dut_id: Optional[int],
    ) -> int:
        resolved_execution_id = execution_id
        if resolved_execution_id is None:
            resolved_execution_id = self._resolve_execution_id(case_path)
        insert_sql = (
            "INSERT INTO `test_report` "
            "(`execution_id`, `dut_id`, `csv_name`, `csv_path`, `data_type`, `case_path`) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        return self._client.insert(
            insert_sql,
            (
                resolved_execution_id,
                dut_id,
                csv_name,
                csv_path,
                data_type,
                case_path,
            ),
        )

    def ensure_schema_initialized(self) -> None:
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
        execution_id: Optional[int] = None,
        dut_id: Optional[int] = None,
    ) -> int:
        logging.info(
            "Sync CSV %s into performance table | headers=%s rows=%s",
            csv_name,
            len(headers),
            len(rows),
        )

        self.ensure_schema_initialized()

        report_id = self._register_test_report(
            csv_name=csv_name,
            csv_path=csv_path,
            data_type=data_type,
            case_path=case_path,
            execution_id=execution_id,
            dut_id=dut_id,
        )
        logging.debug("Created test_report entry id=%s", report_id)

        insert_columns = [name for name, _ in self._BASE_COLUMNS]
        insert_columns.extend(column.name for column in self._STATIC_COLUMNS)
        column_clause = ", ".join(f"`{name}`" for name in insert_columns)
        placeholders = ", ".join(["%s"] * len(insert_columns))
        insert_sql = f"INSERT INTO `{self.TABLE_NAME}` ({column_clause}) VALUES ({placeholders})"

        throughput_aliases = self._collect_throughput_headers(headers)
        values: List[List[Any]] = []
        for row in rows:
            row_values: List[Any] = [
                report_id,
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
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _normalize_upper_token(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.upper()


def _split_fpga(value: Any) -> tuple[Optional[str], Optional[str]]:
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
    details: Dict[str, Optional[str]] = {
        "customer": None,
        "product_line": None,
        "project": None,
        "main_chip": None,
        "wifi_module": None,
        "interface": None,
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

    return details


def _build_dut_payload(config: Mapping[str, Any]) -> Dict[str, Any]:
    software = _extract_first(config, "software_info") or _extract_first(config, "software")
    hardware = _extract_first(config, "hardware_info") or _extract_first(config, "hardware")
    android = _extract_first(config, "android_system") or _extract_first(config, "android")
    connect = _extract_first(config, "connect_type") or {}
    wifi_details = _resolve_wifi_product_details(config.get("fpga"))

    return {
        "software_version": _extract_first(software, "software_version"),
        "driver_version": _extract_first(software, "driver_version"),
        "hardware_version": _extract_first(hardware, "hardware_version"),
        "android_version": _extract_first(android, "version"),
        "kernel_version": _extract_first(android, "kernel_version"),
        "connect_type": connect.get("type") if isinstance(connect, Mapping) else None,
        "adb_device": _extract_first(connect, "adb", "device"),
        "telnet_ip": _extract_first(connect, "telnet", "ip"),
        "product_line": wifi_details.get("product_line"),
        "project": wifi_details.get("project"),
        "main_chip": wifi_details.get("main_chip"),
        "wifi_module": wifi_details.get("wifi_module"),
        "interface": wifi_details.get("interface"),
    }


def _build_execution_payload(config: Mapping[str, Any]) -> Dict[str, Any]:
    router = _extract_first(config, "router") or {}
    rf_solution = config.get("rf_solution") if isinstance(config, Mapping) else {}
    corner_cfg = config.get("corner_angle") if isinstance(config, Mapping) else {}
    lab_info = config.get("lab") if isinstance(config, Mapping) else {}
    case_path = (
        config.get("case_path")
        or config.get("test_case")
        or config.get("text_case")
        or config.get("testcase")
    )
    if isinstance(rf_solution, Mapping):
        rf_model = str(rf_solution.get("model") or "").strip() or None
    else:
        rf_model = None
    if isinstance(corner_cfg, Mapping):
        corner_model = str(corner_cfg.get("model") or "").strip() or None
    else:
        corner_model = None
    lab_name = None
    if isinstance(config, Mapping):
        lab_name = config.get("lab_name")
    if lab_name is None and isinstance(lab_info, Mapping):
        lab_name_value = lab_info.get("name")
        if isinstance(lab_name_value, str):
            lab_name = lab_name_value.strip() or None
        else:
            lab_name = None
    elif isinstance(lab_name, str):
        lab_name = lab_name.strip() or None
    else:
        lab_name = None

    return {
        "case_path": case_path,
        "case_root": None,  # derive later inside sync_config
        "router_name": router.get("name"),
        "router_address": router.get("address"),
        "rf_model": rf_model,
        "corner_model": corner_model,
        "lab_name": lab_name,
    }


def sync_configuration(config: dict | None) -> Optional[Any]:
    """Persist DUT/execution metadata derived from configuration."""

    if not isinstance(config, Mapping) or not config:
        logging.debug("sync_configuration: skipped, config missing or invalid (%s)", type(config))
        return None

    try:
        from src.tools.db_config_sync import ConfigDatabaseSync
    except Exception:
        logging.exception("sync_configuration: failed to import ConfigDatabaseSync")
        return None

    dut_payload = _build_dut_payload(config)
    execution_payload = _build_execution_payload(config)
    logging.debug(
        "sync_configuration: dut_payload=%s execution_payload=%s",
        dut_payload,
        execution_payload,
    )

    try:
        with ConfigDatabaseSync() as syncer:
            result = syncer.sync_config(dut_payload, execution_payload)
    except Exception:
        logging.exception("sync_configuration: failed to persist configuration payloads")
        return None

    logging.info(
        "Configuration synced successfully (dut_id=%s, execution_id=%s)",
        getattr(result, "dut_id", None),
        getattr(result, "execution_id", None),
    )
    return result


def sync_test_result_to_db(
    config: dict | None,
    *,
    log_file: str,
    data_type: Optional[str] = None,
    case_path: Optional[str] = None,
    run_source: str = "local",
) -> int:
    """Load a CSV file and append its rows into the performance table."""

    active_config: Optional[Mapping[str, Any]] = None
    if isinstance(config, Mapping) and config:
        active_config = config
    else:
        try:
            from src.tools import config_loader  # Imported lazily to avoid circular deps

            active_config = config_loader.load_config(refresh=True)
        except Exception:
            logging.debug(
                "sync_test_result_to_db: failed to load configuration for persistence",
                exc_info=True,
            )
            active_config = None

    if active_config:
        sync_result = sync_configuration(active_config)
    else:
        logging.debug("sync_test_result_to_db: no configuration available for database sync.")
        sync_result = None

    execution_hint = getattr(sync_result, "execution_id", None)
    dut_hint = getattr(sync_result, "dut_id", None)

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
                generated = generate_rvr_charts(file_path)
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
                case_path=case_path,
                execution_id=execution_hint,
                dut_id=dut_hint,
            )
        return affected
    except Exception:
        logging.exception("Failed to sync CSV results into performance table")
        return 0


def sync_file_to_db(
    file_path: str,
    data_type: str,
    *,
    config: Optional[dict] = None,
    case_path: Optional[str] = None,
    run_source: str = "FRAMEWORK",
) -> int:
    """Convenience wrapper mirroring :func:`sync_test_result_to_db`."""

    return sync_test_result_to_db(
        config or {},
        log_file=file_path,
        data_type=data_type,
        case_path=case_path,
        run_source=run_source,
    )
