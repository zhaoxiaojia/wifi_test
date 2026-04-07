from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.tools.mysql_tool.client import MySqlClient
from src.tools.mysql_tool.schema import ensure_report_tables, ensure_table, get_table_spec
from src.util.constants import (
    AP_MODEL_CHOICES,
    DUT_OS_CHOICES,
    HW_PHASE_CHOICES,
    LAB_CAPABILITY_CHOICES,
    LAB_ENV_COEX_MODE_CHOICES,
    LAB_ENV_CONNECT_TYPE_CHOICES,
    PROJECT_TYPES,
    RUN_TYPE_CHOICES,
    TEST_REPORT_CHOICES,
)


_TARGET_TABLES: tuple[str, ...] = (
    "project",
    "lab",
    "router",
    "test_report",
    "dut",
    "lab_capability",
    "lab_environment",
    "execution",
    "performance",
    "artifact",
    "perf_metric_kv",
    "compatibility",
)

_LEGACY_TABLE_RENAME_SUFFIX = "__legacy"


def _table_exists(client: MySqlClient, *, table: str) -> bool:
    row = client.query_one(
        "SELECT COUNT(*) AS cnt "
        "FROM information_schema.TABLES "
        "WHERE table_schema = DATABASE() AND table_name = %s",
        (table,),
    )
    return int(row["cnt"]) > 0


def _column_exists(client: MySqlClient, *, table: str, column: str) -> bool:
    row = client.query_one(
        "SELECT COUNT(*) AS cnt "
        "FROM information_schema.COLUMNS "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (table, column),
    )
    return int(row["cnt"]) > 0


def _list_columns(client: MySqlClient, *, table: str) -> list[str]:
    rows = client.query_all(
        "SELECT column_name "
        "FROM information_schema.COLUMNS "
        "WHERE table_schema = DATABASE() AND table_name = %s",
        (table,),
    )
    return [str(r["column_name"]) for r in rows]


def _list_indexes(client: MySqlClient, *, table: str) -> set[str]:
    rows = client.query_all(
        "SELECT DISTINCT index_name "
        "FROM information_schema.STATISTICS "
        "WHERE table_schema = DATABASE() AND table_name = %s",
        (table,),
    )
    return {str(r["index_name"]) for r in rows}


def _list_foreign_keys(client: MySqlClient, *, table: str) -> set[str]:
    rows = client.query_all(
        "SELECT constraint_name "
        "FROM information_schema.REFERENTIAL_CONSTRAINTS "
        "WHERE constraint_schema = DATABASE() AND table_name = %s",
        (table,),
    )
    return {str(r["constraint_name"]) for r in rows}


def _normalize_choice(
    value: Any,
    *,
    allowed: Iterable[str],
    aliases: Mapping[str, str] | None = None,
) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    allowed_tuple = tuple(str(item) for item in allowed)
    if text in allowed_tuple:
        return text
    lowered = text.lower()
    if aliases and lowered in aliases:
        mapped = str(aliases[lowered]).strip()
        if mapped in allowed_tuple:
            return mapped
    for candidate in allowed_tuple:
        if candidate.lower() == lowered:
            return candidate
    return None


def _drop_foreign_key(client: MySqlClient, *, table: str, constraint: str) -> None:
    client.execute(f"ALTER TABLE `{table}` DROP FOREIGN KEY `{constraint}`")


def _drop_index(client: MySqlClient, *, table: str, index: str) -> None:
    client.execute(f"ALTER TABLE `{table}` DROP INDEX `{index}`")


def _drop_column(client: MySqlClient, *, table: str, column: str) -> None:
    client.execute(f"ALTER TABLE `{table}` DROP COLUMN `{column}`")


def _rename_table_if_exists(client: MySqlClient, *, old: str, new: str) -> None:
    if not _table_exists(client, table=old):
        return
    if _table_exists(client, table=new):
        return
    print(f"[MIGRATION] rename_table {old} -> {new}", flush=True)
    client.execute(f"RENAME TABLE `{old}` TO `{new}`")


def _parse_sql_tables(sql_path: Path) -> dict[str, set[str]]:
    text = sql_path.read_text(encoding="utf-8", errors="ignore")
    tables: dict[str, set[str]] = {}
    for match in re.finditer(r"CREATE\s+TABLE\s+`(?P<name>[^`]+)`\s*\(", text, flags=re.IGNORECASE):
        name = match.group("name")
        start = match.end()
        end = text.find(") ENGINE=", start)
        if end == -1:
            continue
        body = text[start:end]
        columns: set[str] = set()
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped.startswith("`"):
                continue
            col = stripped.split("`", 2)[1]
            if col:
                columns.add(col)
        tables[name] = columns
    return tables


def _rename_extra_tables_from_legacy_sql(
    client: MySqlClient, *, legacy_tables: Mapping[str, set[str]]
) -> None:
    target = set(_TARGET_TABLES)
    for table in sorted(legacy_tables):
        if table in target:
            continue
        if not _table_exists(client, table=table):
            continue
        renamed = f"{table}{_LEGACY_TABLE_RENAME_SUFFIX}"
        if _table_exists(client, table=renamed):
            continue
        print(f"[MIGRATION] preserve_extra_table rename {table} -> {renamed}", flush=True)
        client.execute(f"RENAME TABLE `{table}` TO `{renamed}`")


def _expected_columns_for_table(table: str) -> set[str]:
    spec = get_table_spec(table)
    columns = {c.name for c in spec.columns}
    if spec.include_audit_columns:
        columns.update({"created_at", "updated_at"})
    columns.add("id")
    return columns


def _expected_indexes_for_table(table: str) -> set[str]:
    spec = get_table_spec(table)
    names = {i.name for i in spec.indexes}
    for c in spec.constraints:
        if " UNIQUE " in f" {c.definition} ":
            names.add(c.name)
    return names


def _expected_foreign_keys_for_table(table: str) -> set[str]:
    spec = get_table_spec(table)
    return {c.name for c in spec.constraints if "FOREIGN KEY" in c.definition.upper()}


_FK_REF_RE = re.compile(
    r"FOREIGN\s+KEY\s+\(`(?P<col>[^`]+)`\)\s+REFERENCES\s+`(?P<ref_table>[^`]+)`\s+\(`(?P<ref_col>[^`]+)`\)",
    flags=re.IGNORECASE,
)


def _extract_fk_ref(constraint_def: str) -> tuple[str, str, str] | None:
    m = _FK_REF_RE.search(constraint_def)
    if not m:
        return None
    return m.group("col"), m.group("ref_table"), m.group("ref_col")


def _ensure_legacy_project_id(client: MySqlClient) -> int:
    row = client.query_one(
        "SELECT `id` FROM `project` WHERE `customer`=%s AND `project_type`=%s AND `nickname`=%s LIMIT 1",
        ("__legacy__", PROJECT_TYPES[0], "__legacy__"),
    )
    if row and row.get("id") is not None:
        return int(row["id"])

    sql = (
        "INSERT INTO `project` "
        "(`customer`, `project_type`, `nickname`, `project_name`, `project_id`, `odm`) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )
    args = (
        "__legacy__",
        PROJECT_TYPES[0],
        "__legacy__",
        "Legacy Orphans",
        None,
        "__legacy__",
    )
    return int(client.insert(sql, args))


def _ensure_placeholder_test_report(client: MySqlClient, *, desired_id: int | None) -> int:
    legacy_project_id = _ensure_legacy_project_id(client)

    if desired_id is not None and desired_id > 0:
        exists = client.query_one("SELECT COUNT(*) AS cnt FROM `test_report` WHERE `id`=%s", (desired_id,))
        if int(exists["cnt"]) > 0:
            return desired_id

    name = f"legacy_orphan_{desired_id}" if desired_id else "legacy_orphan_auto"
    sql = (
        "INSERT INTO `test_report` "
        + ("(`id`, " if desired_id else "(")
        + "`project_id`, `lab_id`, `report_name`, `case_path`, `is_golden`, `report_type`, `golden_group`, "
        "`notes`, `tester`, `csv_name`, `csv_path`) "
        + ("VALUES (%s, " if desired_id else "VALUES (")
        + "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    args = (
        *((desired_id,) if desired_id else ()),
        legacy_project_id,
        None,
        name,
        None,
        0,
        None,
        None,
        "Auto-created by migration.",
        None,
        None,
        None,
    )
    new_id = int(client.insert(sql, args))
    return new_id


def _ensure_fk_ref_integrity(client: MySqlClient, *, table: str, constraint_defs: Iterable[str]) -> None:
    for constraint_def in constraint_defs:
        ref = _extract_fk_ref(constraint_def)
        if not ref:
            continue
        col, ref_table, ref_col = ref
        if ref_col != "id":
            continue
        if not _table_exists(client, table=table) or not _table_exists(client, table=ref_table):
            continue
        if not _column_exists(client, table=table, column=col):
            continue

        if ref_table == "test_report":
            rows = client.query_all(
                f"""
                SELECT DISTINCT t.`{col}` AS missing_id
                FROM `{table}` AS t
                LEFT JOIN `{ref_table}` AS r ON r.`id` = t.`{col}`
                WHERE t.`{col}` IS NOT NULL AND r.`id` IS NULL
                """
            )
            if not rows:
                continue
            missing_ids = sorted(int(r["missing_id"]) for r in rows if r.get("missing_id") is not None)
            preview = ", ".join(str(x) for x in missing_ids[:20])
            print(f"[MIGRATION] fk_preflight table={table} col={col} orphans={len(missing_ids)} ids={preview}", flush=True)
            for missing_id in missing_ids:
                if missing_id <= 0:
                    new_id = _ensure_placeholder_test_report(client, desired_id=None)
                    client.execute(
                        f"UPDATE `{table}` SET `{col}`=%s WHERE `{col}`=%s",
                        (new_id, missing_id),
                    )
                    print(
                        f"[MIGRATION] fk_fix table={table} col={col} old_id={missing_id} new_id={new_id}",
                        flush=True,
                    )
                else:
                    _ensure_placeholder_test_report(client, desired_id=missing_id)


def _migrate_test_case_table(client: MySqlClient) -> None:
    if not _table_exists(client, table="test_case"):
        return
    if not _table_exists(client, table="test_report"):
        return

    src_cols = set(_list_columns(client, table="test_case"))
    dst_cols = set(_list_columns(client, table="test_report"))
    wanted = [
        "project_id",
        "report_name",
        "case_path",
        "is_golden",
        "report_type",
        "golden_group",
        "notes",
        "tester",
        "csv_name",
        "csv_path",
    ]
    common = [c for c in wanted if c in src_cols and c in dst_cols]
    if not common:
        return

    print(f"[MIGRATION] migrate_table test_case -> test_report columns={','.join(common)}", flush=True)
    select_list = ", ".join(f"tc.`{c}`" for c in common)
    insert_list = ", ".join(f"`{c}`" for c in common)
    client.execute(
        f"INSERT IGNORE INTO `test_report` ({insert_list}) SELECT {select_list} FROM `test_case` AS tc"
    )

    print("[MIGRATION] drop_table test_case", flush=True)
    client.execute("DROP TABLE `test_case`")


def _migrate_project_data(client: MySqlClient) -> None:
    if not _table_exists(client, table="project"):
        return
    columns = set(_list_columns(client, table="project"))
    if "customer" in columns and "brand" in columns:
        client.execute(
            "UPDATE `project` SET `customer`=`brand` "
            "WHERE (`customer` IS NULL OR `customer`='') AND `brand` IS NOT NULL AND `brand`<>''"
        )
    if "odm" in columns and "brand" in columns:
        client.execute(
            "UPDATE `project` SET `odm`=`brand` "
            "WHERE (`odm` IS NULL OR `odm`='') AND `brand` IS NOT NULL AND `brand`<>''"
        )
    if "project_type" in columns and "product_line" in columns:
        client.execute(
            "UPDATE `project` SET `project_type`=`product_line` "
            "WHERE (`project_type` IS NULL OR `project_type`='') "
            "AND `product_line` IS NOT NULL AND `product_line`<>''"
        )
    if "soc" in columns and "main_chip" in columns:
        client.execute(
            "UPDATE `project` SET `soc`=`main_chip` "
            "WHERE (`soc` IS NULL OR `soc`='') AND `main_chip` IS NOT NULL AND `main_chip`<>''"
        )


def _migrate_lab_data(client: MySqlClient) -> None:
    if not _table_exists(client, table="lab"):
        return
    columns = set(_list_columns(client, table="lab"))
    if "turntable" in columns and "turntable_model" in columns:
        client.execute(
            "UPDATE `lab` SET `turntable`=`turntable_model` "
            "WHERE (`turntable` IS NULL OR `turntable`='') "
            "AND `turntable_model` IS NOT NULL AND `turntable_model`<>''"
        )
    if "attenuator" in columns and "rf_model" in columns:
        client.execute(
            "UPDATE `lab` SET `attenuator`=`rf_model` "
            "WHERE (`attenuator` IS NULL OR `attenuator`='') "
            "AND `rf_model` IS NOT NULL AND `rf_model`<>''"
        )


def _migrate_lab_capabilities(client: MySqlClient) -> None:
    if not _table_exists(client, table="lab") or not _table_exists(client, table="lab_capability"):
        return
    if not _column_exists(client, table="lab", column="capabilities"):
        return
    capability_aliases = {
        "rvr": "RVR",
        "rvo": "RVO",
        "peak_throughput": "Peak Throughput",
        "peak throughput": "Peak Throughput",
        "performance": "Peak Throughput",
        "ota": "OTA",
        "noise": "NOISE",
        "rf": "RF",
        "compatibility": "Compatibility",
    }
    rows = client.query_all("SELECT `id`, `capabilities` FROM `lab` WHERE `capabilities` IS NOT NULL")
    inserts: list[tuple[int, str]] = []
    for row in rows:
        if row.get("id") is None:
            continue
        lab_id = int(row["id"])
        raw = row.get("capabilities")
        parsed: list[Any]
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                continue
            try:
                loaded = json.loads(text)
            except Exception:
                loaded = [part.strip() for part in text.split(",") if part.strip()]
            if isinstance(loaded, list):
                parsed = loaded
            else:
                parsed = [loaded]
        elif isinstance(raw, list):
            parsed = raw
        else:
            continue
        seen: set[str] = set()
        for item in parsed:
            normalized = _normalize_choice(item, allowed=LAB_CAPABILITY_CHOICES, aliases=capability_aliases)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            inserts.append((lab_id, normalized))
    if inserts:
        client.executemany(
            "INSERT IGNORE INTO `lab_capability` (`lab_id`, `capability`) VALUES (%s, %s)",
            inserts,
        )


def _migrate_test_report_data(client: MySqlClient) -> None:
    if not _table_exists(client, table="test_report"):
        return
    test_report_cols = set(_list_columns(client, table="test_report"))
    execution_cols = set(_list_columns(client, table="execution")) if _table_exists(client, table="execution") else set()
    if "lab_id" in test_report_cols and "lab_id" in execution_cols:
        client.execute(
            """
            UPDATE `test_report` AS tr
            JOIN (
                SELECT `test_report_id`, MAX(`lab_id`) AS `lab_id`
                FROM `execution`
                WHERE `lab_id` IS NOT NULL
                GROUP BY `test_report_id`
            ) AS src ON src.`test_report_id` = tr.`id`
            SET tr.`lab_id` = src.`lab_id`
            WHERE tr.`lab_id` IS NULL
            """
        )
    if "report_type" in test_report_cols and "execution_type" in execution_cols:
        client.execute(
            """
            UPDATE `test_report` AS tr
            JOIN (
                SELECT `test_report_id`, MAX(`execution_type`) AS `execution_type`
                FROM `execution`
                WHERE `execution_type` IS NOT NULL AND `execution_type` <> ''
                GROUP BY `test_report_id`
            ) AS src ON src.`test_report_id` = tr.`id`
            SET tr.`report_type` = src.`execution_type`
            WHERE tr.`report_type` IS NULL OR tr.`report_type` = ''
            """
        )
    if "csv_name" in test_report_cols and "csv_name" in execution_cols:
        client.execute(
            """
            UPDATE `test_report` AS tr
            JOIN (
                SELECT `test_report_id`, MAX(`csv_name`) AS `csv_name`
                FROM `execution`
                WHERE `csv_name` IS NOT NULL AND `csv_name` <> ''
                GROUP BY `test_report_id`
            ) AS src ON src.`test_report_id` = tr.`id`
            SET tr.`csv_name` = src.`csv_name`
            WHERE tr.`csv_name` IS NULL OR tr.`csv_name` = ''
            """
        )
    if "csv_path" in test_report_cols and "csv_path" in execution_cols:
        client.execute(
            """
            UPDATE `test_report` AS tr
            JOIN (
                SELECT `test_report_id`, MAX(`csv_path`) AS `csv_path`
                FROM `execution`
                WHERE `csv_path` IS NOT NULL AND `csv_path` <> ''
                GROUP BY `test_report_id`
            ) AS src ON src.`test_report_id` = tr.`id`
            SET tr.`csv_path` = src.`csv_path`
            WHERE tr.`csv_path` IS NULL OR tr.`csv_path` = ''
            """
        )


def _migrate_dut_data(client: MySqlClient) -> None:
    if not _table_exists(client, table="dut"):
        return
    columns = set(_list_columns(client, table="dut"))
    if "sn" in columns and "serial_number" in columns:
        client.execute(
            "UPDATE `dut` SET `sn`=`serial_number` "
            "WHERE (`sn` IS NULL OR `sn`='') AND `serial_number` IS NOT NULL AND `serial_number`<>''"
        )
    if "ip" in columns and "telnet_ip" in columns:
        client.execute(
            "UPDATE `dut` SET `ip`=`telnet_ip` "
            "WHERE (`ip` IS NULL OR `ip`='') AND `telnet_ip` IS NOT NULL AND `telnet_ip`<>''"
        )
    if "hw_phase" in columns and "mass_production_status" in columns:
        rows = client.query_all(
            "SELECT `id`, `mass_production_status` FROM `dut` "
            "WHERE (`hw_phase` IS NULL OR `hw_phase`='') "
            "AND `mass_production_status` IS NOT NULL AND `mass_production_status`<>''"
        )
        phase_aliases = {
            "dvt_rework": "DVT-REWORK",
            "dvt-rework": "DVT-REWORK",
        }
        for row in rows:
            normalized = _normalize_choice(
                row.get("mass_production_status"),
                allowed=HW_PHASE_CHOICES,
                aliases=phase_aliases,
            )
            if normalized:
                client.execute("UPDATE `dut` SET `hw_phase`=%s WHERE `id`=%s", (normalized, int(row["id"])))
    if "os" in columns and "connect_type" in columns:
        os_aliases = {"android": "rdk", "linux": "rdk"}
        rows = client.query_all(
            "SELECT `id`, `connect_type` FROM `dut` "
            "WHERE (`os` IS NULL OR `os`='') "
            "AND `connect_type` IS NOT NULL AND `connect_type`<>''"
        )
        for row in rows:
            normalized = _normalize_choice(row.get("connect_type"), allowed=DUT_OS_CHOICES, aliases=os_aliases)
            if normalized:
                client.execute("UPDATE `dut` SET `os`=%s WHERE `id`=%s", (normalized, int(row["id"])))


def _migrate_lab_environment_data(client: MySqlClient) -> None:
    if not _table_exists(client, table="lab_environment"):
        return
    env_cols = set(_list_columns(client, table="lab_environment"))
    execution_cols = set(_list_columns(client, table="execution")) if _table_exists(client, table="execution") else set()
    if "ap_name" in env_cols and "router_name" in env_cols:
        ap_aliases = {
            "asusax86u": "ASUS-AX86U",
            "asus-ax86u": "ASUS-AX86U",
            "asusax88u": "ASUS-AX88U",
            "asus-ax88u": "ASUS-AX88U",
            "asusax88upro": "ASUS-AX88U Pro",
            "asus-ax88u pro": "ASUS-AX88U Pro",
            "asus-ax88upro": "ASUS-AX88U Pro",
            "xiaomiax3600": "Xiaomi AX3600",
            "xiaomi ax3600": "Xiaomi AX3600",
            "xiaomiax7000": "Xiaomi AX7000",
            "xiaomibe7000": "Xiaomi AX7000",
            "xiaomi ax7000": "Xiaomi AX7000",
            "glmt3000": "Glmt3000",
        }
        rows = client.query_all(
            "SELECT `id`, `router_name` FROM `lab_environment` "
            "WHERE (`ap_name` IS NULL OR `ap_name`='') AND `router_name` IS NOT NULL AND `router_name`<>''"
        )
        for row in rows:
            normalized = _normalize_choice(
                str(row.get("router_name") or "").replace(" ", "").replace("_", "").replace("-", ""),
                allowed=AP_MODEL_CHOICES,
                aliases=ap_aliases,
            )
            if normalized:
                client.execute("UPDATE `lab_environment` SET `ap_name`=%s WHERE `id`=%s", (normalized, int(row["id"])))
    if "ap_address" in env_cols and "router_address" in env_cols:
        client.execute(
            "UPDATE `lab_environment` SET `ap_address`=`router_address` "
            "WHERE (`ap_address` IS NULL OR `ap_address`='') AND `router_address` IS NOT NULL AND `router_address`<>''"
        )
    if "connect_type" in env_cols and "connect_type" in execution_cols:
        rows = client.query_all(
            """
            SELECT le.`id`, ex.`connect_type`
            FROM `lab_environment` AS le
            JOIN `execution` AS ex ON ex.`lab_id` = le.`lab_id`
            WHERE (le.`connect_type` IS NULL OR le.`connect_type` = '')
              AND ex.`connect_type` IS NOT NULL AND ex.`connect_type` <> ''
            ORDER BY ex.`id` DESC
            """
        )
        connect_aliases = {
            "adb": "Direct Plug-in",
            "android": "Direct Plug-in",
            "linux": "HDMI Extension",
            "telnet": "HDMI Extension",
            "no hdmi": "NO HDMI",
        }
        updated: set[int] = set()
        for row in rows:
            env_id = int(row["id"])
            if env_id in updated:
                continue
            normalized = _normalize_choice(
                row.get("connect_type"),
                allowed=LAB_ENV_CONNECT_TYPE_CHOICES,
                aliases=connect_aliases,
            )
            if normalized:
                client.execute("UPDATE `lab_environment` SET `connect_type`=%s WHERE `id`=%s", (normalized, env_id))
                updated.add(env_id)
    if "coex_mode" in env_cols and "bt_mode" in execution_cols:
        rows = client.query_all(
            """
            SELECT le.`id`, ex.`bt_mode`
            FROM `lab_environment` AS le
            JOIN `execution` AS ex ON ex.`lab_id` = le.`lab_id`
            WHERE (le.`coex_mode` IS NULL OR le.`coex_mode` = '')
              AND ex.`bt_mode` IS NOT NULL AND ex.`bt_mode` <> ''
            ORDER BY ex.`id` DESC
            """
        )
        coex_aliases = {
            "off": "WiFi Only",
            "wifi only": "WiFi Only",
            "ble": "WiFi+BLE",
            "classic": "WiFi+CLASSIC",
            "dual": "WiFi+BLE+CLASSIC",
            "ble+classic": "WiFi+BLE+CLASSIC",
        }
        updated: set[int] = set()
        for row in rows:
            env_id = int(row["id"])
            if env_id in updated:
                continue
            normalized = _normalize_choice(
                row.get("bt_mode"),
                allowed=LAB_ENV_COEX_MODE_CHOICES,
                aliases=coex_aliases,
            )
            if normalized:
                client.execute("UPDATE `lab_environment` SET `coex_mode`=%s WHERE `id`=%s", (normalized, env_id))
                updated.add(env_id)


def _migrate_performance_data(client: MySqlClient) -> None:
    if not _table_exists(client, table="performance"):
        return
    columns = set(_list_columns(client, table="performance"))
    rename_pairs = (
        ("serial_number", "serial_number"),
        ("standard", "wifi_mode"),
        ("center_freq_mhz", "channel"),
        ("path_loss_db", "attenuation"),
        ("angle_deg", "angle"),
    )
    for old_name, new_name in rename_pairs:
        if old_name in columns and new_name in columns and old_name != new_name:
            client.execute(
                f"UPDATE `performance` SET `{new_name}`=`{old_name}` "
                f"WHERE `{new_name}` IS NULL AND `{old_name}` IS NOT NULL"
            )
    if "execution_id" in columns and "test_report_id" in columns and _table_exists(client, table="execution"):
        client.execute(
            """
            UPDATE `performance` AS p
            JOIN `execution` AS ex ON ex.`id` = p.`execution_id`
            SET p.`test_report_id` = ex.`test_report_id`
            WHERE (p.`test_report_id` IS NULL OR p.`test_report_id` = 0)
            """
        )


def _migrate_execution_run_type(client: MySqlClient) -> None:
    if not _table_exists(client, table="execution") or not _column_exists(client, table="execution", column="run_type"):
        return
    rows = client.query_all(
        "SELECT `id`, `run_type` FROM `execution` WHERE `run_type` IS NOT NULL AND `run_type` <> ''"
    )
    aliases = {
        "wifi-smarttest": "WIFI-SmartTest",
        "smarttest": "WIFI-SmartTest",
        "di": "DI",
    }
    for row in rows:
        normalized = _normalize_choice(row.get("run_type"), allowed=RUN_TYPE_CHOICES, aliases=aliases)
        if normalized and normalized != row.get("run_type"):
            client.execute("UPDATE `execution` SET `run_type`=%s WHERE `id`=%s", (normalized, int(row["id"])))


def _migrate_test_report_type_values(client: MySqlClient) -> None:
    if not _table_exists(client, table="test_report") or not _column_exists(client, table="test_report", column="report_type"):
        return
    aliases = {
        "performance": "Peak Throughput",
        "peak_throughput": "Peak Throughput",
        "peak throughput": "Peak Throughput",
        "compatibility": "Compatibility",
        "rvr": "RVR",
        "rvo": "RVO",
        "ota": "OTA",
        "noise": "NOISE",
        "rf": "RF",
    }
    rows = client.query_all(
        "SELECT `id`, `report_type` FROM `test_report` WHERE `report_type` IS NOT NULL AND `report_type` <> ''"
    )
    for row in rows:
        normalized = _normalize_choice(row.get("report_type"), allowed=TEST_REPORT_CHOICES, aliases=aliases)
        if normalized and normalized != row.get("report_type"):
            client.execute("UPDATE `test_report` SET `report_type`=%s WHERE `id`=%s", (normalized, int(row["id"])))


def _migrate_current_schema_data(client: MySqlClient) -> None:
    _migrate_project_data(client)
    _migrate_lab_data(client)
    _migrate_lab_capabilities(client)
    _migrate_test_report_data(client)
    _migrate_test_report_type_values(client)
    _migrate_dut_data(client)
    _migrate_lab_environment_data(client)
    _migrate_performance_data(client)
    _migrate_execution_run_type(client)


def _drop_redundancy_against_target(client: MySqlClient) -> int:
    changes = 0
    for table in _TARGET_TABLES:
        if not _table_exists(client, table=table):
            continue

        expected_cols = _expected_columns_for_table(table)
        actual_cols = set(_list_columns(client, table=table))
        extra_cols = sorted(c for c in actual_cols - expected_cols if c not in {"id"})

        expected_fks = _expected_foreign_keys_for_table(table)
        actual_fks = _list_foreign_keys(client, table=table)
        extra_fks = sorted(actual_fks - expected_fks)

        expected_indexes = _expected_indexes_for_table(table)
        actual_indexes = _list_indexes(client, table=table)
        extra_indexes = sorted(i for i in actual_indexes - expected_indexes if i != "PRIMARY")

        for fk in extra_fks:
            print(f"[MIGRATION] drop_fk table={table} fk={fk}", flush=True)
            _drop_foreign_key(client, table=table, constraint=fk)
            changes += 1

        for idx in extra_indexes:
            print(f"[MIGRATION] drop_index table={table} index={idx}", flush=True)
            _drop_index(client, table=table, index=idx)
            changes += 1

        for col in extra_cols:
            print(f"[MIGRATION] drop_column table={table} column={col}", flush=True)
            _drop_column(client, table=table, column=col)
            changes += 1

    return changes


def _compute_diff_summary(client: MySqlClient) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for table in _TARGET_TABLES:
        if not _table_exists(client, table=table):
            out[table] = {"missing_table": True}
            continue
        expected_cols = _expected_columns_for_table(table)
        actual_cols = set(_list_columns(client, table=table))
        expected_fks = _expected_foreign_keys_for_table(table)
        actual_fks = _list_foreign_keys(client, table=table)
        expected_indexes = _expected_indexes_for_table(table)
        actual_indexes = _list_indexes(client, table=table)
        out[table] = {
            "extra_cols": sorted(actual_cols - expected_cols),
            "missing_cols": sorted(expected_cols - actual_cols),
            "extra_fks": sorted(actual_fks - expected_fks),
            "missing_fks": sorted(expected_fks - actual_fks),
            "extra_indexes": sorted((actual_indexes - expected_indexes) - {"PRIMARY"}),
            "missing_indexes": sorted(expected_indexes - actual_indexes),
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Converge MySQL schema to schema.py TableSpec.")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--cleanup-legacy", action="store_true")
    parser.add_argument(
        "--legacy-sql",
        default=None,
        help="Path to a legacy MySQL dump (schema-only or full) used to drive cleanup decisions.",
    )
    parser.add_argument("--max-rounds", type=int, default=5)
    args = parser.parse_args(argv)

    client = MySqlClient(autocommit=True)

    legacy_tables: dict[str, set[str]] = {}
    if args.legacy_sql:
        path = Path(args.legacy_sql)
        if path.is_file():
            legacy_tables = _parse_sql_tables(path)
            print(f"[MIGRATION] legacy_sql={args.legacy_sql}", flush=True)

    print("[MIGRATION] phase=1 legacy_cleanup start", flush=True)
    if args.cleanup_legacy:
        _rename_table_if_exists(client, old="lab_enviroment", new="lab_environment")
    if legacy_tables:
        _rename_extra_tables_from_legacy_sql(client, legacy_tables=legacy_tables)
    _migrate_test_case_table(client)
    print("[MIGRATION] phase=1 legacy_cleanup done", flush=True)

    for round_idx in range(int(args.max_rounds)):
        print(f"[MIGRATION] phase=2 converge round={round_idx+1} start", flush=True)

        for table in _TARGET_TABLES:
            if not _table_exists(client, table=table):
                print(f"[MIGRATION] ensure_table create_missing table={table}", flush=True)
                ensure_table(client, table, get_table_spec(table))

        print(f"[MIGRATION] ensure_report_tables round={round_idx+1} pre_migrate start", flush=True)
        ensure_report_tables(client)
        print(f"[MIGRATION] ensure_report_tables round={round_idx+1} pre_migrate done", flush=True)

        print(f"[MIGRATION] data_migrate round={round_idx+1} start", flush=True)
        _migrate_current_schema_data(client)
        print(f"[MIGRATION] data_migrate round={round_idx+1} done", flush=True)

        for table in _TARGET_TABLES:
            spec = get_table_spec(table)
            fk_defs = [c.definition for c in spec.constraints if "FOREIGN KEY" in c.definition.upper()]
            _ensure_fk_ref_integrity(client, table=table, constraint_defs=fk_defs)

        changes = _drop_redundancy_against_target(client)
        print(f"[MIGRATION] converge round={round_idx+1} dropped_items={changes}", flush=True)

        print(f"[MIGRATION] ensure_report_tables round={round_idx+1} finalize start", flush=True)
        ensure_report_tables(client)
        print(f"[MIGRATION] ensure_report_tables round={round_idx+1} finalize done", flush=True)

        diffs = _compute_diff_summary(client)
        remaining = 0
        for table, info in diffs.items():
            if info.get("missing_table"):
                remaining += 1
                continue
            for key in ("extra_cols", "missing_cols", "extra_fks", "missing_fks", "extra_indexes", "missing_indexes"):
                if info.get(key):
                    remaining += 1
                    break
        print(f"[MIGRATION] phase=2 converge round={round_idx+1} remaining_tables_with_diff={remaining}", flush=True)
        if remaining == 0:
            print("[MIGRATION] converge status=ok", flush=True)
            return 0

    print("[MIGRATION] converge status=not_converged", flush=True)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
