from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Mapping

from .client import MySqlClient
from .models import HeaderMapping
from .naming import IdentifierBuilder
from .schema import ensure_report_tables, read_csv_rows

__all__ = [
    "PerformanceTableManager",
    "sync_configuration",
    "sync_test_result_to_db",
    "sync_file_to_db",
]


@dataclass(frozen=True)
class _ColumnInfo:
    mapping: HeaderMapping
    sql_type: str


class PerformanceTableManager:
    """Manage the performance table with dynamic schema extension and cumulative writes."""

    TABLE_NAME = "performance"
    REPORT_TABLE_NAME = "test_report"

    _BASE_COLUMNS: Sequence[tuple[str, str]] = (
        ("test_report_id", "INT NOT NULL"),
        ("csv_name", "VARCHAR(255) NOT NULL"),
        ("data_type", "VARCHAR(64) NULL DEFAULT NULL"),
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

    @classmethod
    def _infer_sql_type(cls, values: Iterable[Any]) -> str:
        seen_float = False
        seen_int = False
        for value in values:
            value_type, _ = cls._classify_value(value)
            if value_type == "json":
                return "JSON"
            if value_type == "text":
                return "TEXT"
            if value_type == "float":
                seen_float = True
            elif value_type == "int":
                seen_int = True
        if seen_float:
            return "DOUBLE"
        if seen_int:
            return "BIGINT"
        return "TEXT"

    @staticmethod
    def _canonical_sql_type(sql_type: str) -> str:
        normalized = (sql_type or "").upper()
        if normalized.startswith("DOUBLE"):
            return "DOUBLE"
        if normalized.startswith("BIGINT") or normalized.startswith("INT"):
            return "BIGINT"
        if normalized.startswith("JSON"):
            return "JSON"
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
        if canonical == "BIGINT":
            if value_type == "int":
                return int(parsed)
            if value_type == "float":
                float_value = float(parsed)
                if float_value.is_integer():
                    return int(float_value)
            return None
        return str(parsed)

    @staticmethod
    def _build_mappings(headers: Sequence[str]) -> List[HeaderMapping]:
        builder = IdentifierBuilder()
        reserved = {name for name, _ in PerformanceTableManager._BASE_COLUMNS}
        used = set(reserved)
        mappings: List[HeaderMapping] = []
        for header in headers:
            if not header:
                continue
            candidate = builder.build((header,), fallback="column")
            if candidate in used:
                candidate = builder.build((header, "field"), fallback="column")
            while candidate in used:
                candidate = builder.build((header, str(len(used))), fallback="column")
            used.add(candidate)
            mappings.append(HeaderMapping(original=header, sanitized=candidate))
        return mappings

    def _prepare_columns(
        self, mappings: Sequence[HeaderMapping], rows: Sequence[Dict[str, Any]]
    ) -> List[_ColumnInfo]:
        columns: List[_ColumnInfo] = []
        for mapping in mappings:
            values = [row.get(mapping.original) for row in rows]
            sql_type = self._infer_sql_type(values)
            columns.append(_ColumnInfo(mapping=mapping, sql_type=sql_type))
        return columns

    def _describe_columns(self) -> Dict[str, Dict[str, Any]]:
        return {
            column["Field"]: column
            for column in self._client.query_all(f"SHOW FULL COLUMNS FROM `{self.TABLE_NAME}`")
        }

    def _ensure_column(self, existing: Dict[str, Dict[str, Any]], column: _ColumnInfo) -> str:
        name = column.mapping.sanitized
        comment = column.mapping.original.replace("'", "''")
        target_type = column.sql_type
        if name not in existing:
            self._client.execute(
                f"ALTER TABLE `{self.TABLE_NAME}` "
                f"ADD COLUMN `{name}` {target_type} NULL DEFAULT NULL COMMENT '{comment}'"
            )
            existing = self._describe_columns()
            return PerformanceTableManager._canonical_sql_type(existing[name]["Type"])
        current_type = PerformanceTableManager._canonical_sql_type(existing[name]["Type"])
        if current_type == target_type:
            return current_type
        if current_type == "TEXT":
            return current_type
        self._client.execute(
            f"ALTER TABLE `{self.TABLE_NAME}` "
            f"MODIFY COLUMN `{name}` TEXT NULL DEFAULT NULL COMMENT '{comment}'"
        )
        existing = self._describe_columns()
        return PerformanceTableManager._canonical_sql_type(existing[name]["Type"])

    def _ensure_columns(self, columns: Sequence[_ColumnInfo]) -> List[_ColumnInfo]:
        if not columns:
            return []
        snapshot = self._describe_columns()
        adjusted: List[_ColumnInfo] = []
        for column in columns:
            canonical = self._ensure_column(snapshot, column)
            snapshot = self._describe_columns()
            adjusted.append(_ColumnInfo(mapping=column.mapping, sql_type=canonical))
        return adjusted

    def _resolve_execution_id(
        self, case_path: Optional[str], csv_path: Optional[str]
    ) -> Optional[int]:
        queries = []
        if csv_path:
            queries.append(
                (
                    "SELECT id FROM `execution` WHERE csv_path = %s ORDER BY id DESC LIMIT 1",
                    (csv_path,),
                )
            )
        if case_path:
            queries.append(
                (
                    "SELECT id FROM `execution` WHERE case_path = %s ORDER BY id DESC LIMIT 1",
                    (case_path,),
                )
            )
        for sql, params in queries:
            try:
                row = self._client.query_one(sql, params)
            except Exception:
                logging.debug("Failed to resolve execution id via %s", sql, exc_info=True)
                continue
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
            resolved_execution_id = self._resolve_execution_id(case_path, csv_path)
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

        report_id = self._register_test_report(
            csv_name=csv_name,
            csv_path=csv_path,
            data_type=data_type,
            case_path=case_path,
            execution_id=execution_id,
            dut_id=dut_id,
        )
        logging.debug("Created test_report entry id=%s", report_id)

        mappings = self._build_mappings(headers)
        column_infos = self._prepare_columns(mappings, rows)
        prepared_columns = self._ensure_columns(column_infos)

        insert_columns = [name for name, _ in self._BASE_COLUMNS]
        insert_columns.extend(info.mapping.sanitized for info in prepared_columns)
        column_clause = ", ".join(f"`{name}`" for name in insert_columns)
        placeholders = ", ".join(["%s"] * len(insert_columns))
        insert_sql = f"INSERT INTO `{self.TABLE_NAME}` ({column_clause}) VALUES ({placeholders})"

        values: List[List[Any]] = []
        for row in rows:
            row_values: List[Any] = [
                report_id,
                csv_name,
                data_type,
            ]
            for info in prepared_columns:
                row_values.append(
                    self._normalize_cell(row.get(info.mapping.original), info.sql_type)
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


def _split_fpga(value: Any) -> tuple[Optional[str], Optional[str]]:
    if isinstance(value, Mapping):
        return (
            str(value.get("series")) if value.get("series") is not None else None,
            str(value.get("interface")) if value.get("interface") is not None else None,
        )
    if isinstance(value, str):
        parts = value.split("_", 1)
        series = parts[0] if parts and parts[0] else None
        interface = parts[1] if len(parts) > 1 else None
        return series, interface
    return None, None


def _build_dut_payload(config: Mapping[str, Any]) -> Dict[str, Any]:
    software = _extract_first(config, "software_info") or _extract_first(config, "software")
    hardware = _extract_first(config, "hardware_info") or _extract_first(config, "hardware")
    android = _extract_first(config, "android_system") or _extract_first(config, "android")
    connect = _extract_first(config, "connect_type") or {}
    third_party = _extract_first(connect, "third_party") or {}
    serial = _extract_first(config, "serial_port") or {}
    fpga_series, fpga_interface = _split_fpga(config.get("fpga"))

    return {
        "software_version": _extract_first(software, "software_version"),
        "driver_version": _extract_first(software, "driver_version"),
        "hardware_version": _extract_first(hardware, "hardware_version"),
        "android_version": _extract_first(android, "version"),
        "kernel_version": _extract_first(android, "kernel_version"),
        "connect_type": connect.get("type") if isinstance(connect, Mapping) else None,
        "adb_device": _extract_first(connect, "adb", "device"),
        "telnet_ip": _extract_first(connect, "telnet", "ip"),
        "third_party_enabled": third_party.get("enabled"),
        "third_party_wait": third_party.get("wait_seconds"),
        "fpga_series": fpga_series,
        "fpga_interface": fpga_interface,
        "serial_port_status": serial.get("status"),
        "serial_port_port": serial.get("port"),
        "serial_port_baud": serial.get("baud"),
    }


def _build_execution_payload(config: Mapping[str, Any]) -> Dict[str, Any]:
    router = _extract_first(config, "router") or {}
    csv_path = config.get("csv_path") or config.get("performance_csv")
    case_path = (
        config.get("case_path")
        or config.get("test_case")
        or config.get("text_case")
        or config.get("testcase")
    )
    return {
        "case_path": case_path,
        "case_root": None,  # derive later inside sync_config
        "router_name": router.get("name"),
        "router_address": router.get("address"),
        "csv_path": csv_path,
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
