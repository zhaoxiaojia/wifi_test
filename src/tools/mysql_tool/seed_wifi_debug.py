from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Mapping, Sequence, Tuple

import pymysql
from pymysql.cursors import DictCursor

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if __package__ is None or __package__ == "":
    PROJECT_ROOT_STR = str(PROJECT_ROOT)
    if PROJECT_ROOT_STR not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_STR)

from src.tools.mysql_tool.config import load_mysql_config
from src.tools.mysql_tool.schema import ensure_report_tables, get_schema_catalog, render_schema_markdown


@dataclass(frozen=True)
class SeedPlan:
    runs_per_case: int
    perf_reports_per_project: int
    compat_reports_per_project: int
    other_reports_per_project: int
    perf_rows_per_run: int
    kv_rows_per_run: int
    compat_rows_per_run: int
    golden_perf_reports_per_project: int
    duts_min_per_project: int
    duts_max_per_project: int
    inject_rvr_rv0: bool


@dataclass(frozen=True)
class SeededProject:
    id: int
    customer: str
    project_type: str
    project_name: str
    soc: str
    wifi_module: str
    interface: str


def _slug(value: str) -> str:
    return (
        str(value)
        .strip()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )


def _random_datetime_tag(*, days_back: int = 60) -> str:
    now = datetime.now(timezone.utc)
    earliest = now - timedelta(days=int(days_back))
    span_seconds = int((now - earliest).total_seconds())
    offset = random.randint(0, max(0, span_seconds))
    dt = earliest + timedelta(seconds=offset)
    return dt.strftime("%Y%m%d_%H%M%S")


def _random_utc_datetime(*, days_back: int = 365) -> datetime:
    now = datetime.now(timezone.utc)
    earliest = now - timedelta(days=int(days_back))
    span_seconds = int((now - earliest).total_seconds())
    offset = random.randint(0, max(0, span_seconds))
    return earliest + timedelta(seconds=offset, microseconds=random.randint(0, 999_999))


def _load_projects(cursor) -> List[SeededProject]:
    cursor.execute(
        "SELECT id, customer, project_type, nickname AS project_name, soc, wifi_module, interface "
        "FROM `project` ORDER BY id ASC"
    )
    projects: List[SeededProject] = []
    for row in cursor.fetchall():
        projects.append(
            SeededProject(
                id=int(row["id"]),
                customer=str(row.get("customer") or ""),
                project_type=str(row.get("project_type") or ""),
                project_name=str(row.get("project_name") or ""),
                soc=str(row.get("soc") or ""),
                wifi_module=str(row.get("wifi_module") or ""),
                interface=str(row.get("interface") or ""),
            )
        )
    return projects


def _load_router_ids(cursor) -> List[int]:
    cursor.execute("SELECT id FROM `router` ORDER BY id ASC")
    return [int(row["id"]) for row in cursor.fetchall()]


def _load_lab_ids(cursor) -> List[int]:
    cursor.execute("SELECT id FROM `lab` ORDER BY id ASC")
    return [int(row["id"]) for row in cursor.fetchall()]


def _utc_run_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _connect_database(config: Mapping[str, object], *, database: str, autocommit: bool = False):
    return pymysql.connect(
        host=str(config["host"]),
        port=int(config.get("port", 3306)),
        user=str(config["user"]),
        password=str(config["password"]),
        database=database,
        charset=config.get("charset", "utf8mb4"),
        autocommit=autocommit,
        cursorclass=DictCursor,
    )


def _chunks(items: Sequence[Sequence[object]], chunk_size: int) -> Iterable[Sequence[Sequence[object]]]:
    for start in range(0, len(items), chunk_size):
        yield items[start : start + chunk_size]


def _insert_many(
    cursor,
    table: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[object]],
    *,
    chunk_size: int = 2000,
) -> int:
    cols = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO `{table}` ({cols}) VALUES ({placeholders})"
    affected = 0
    for batch in _chunks(rows, chunk_size):
        affected += cursor.executemany(sql, batch)
    return affected


def _ensure_columns(cursor, table: str, column_definitions: Mapping[str, str]) -> None:
    cursor.execute(f"SHOW COLUMNS FROM `{table}`")
    existing = {row["Field"] for row in cursor.fetchall()}
    for name, definition in column_definitions.items():
        if name in existing:
            continue
        cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{name}` {definition}")


def _ensure_dut_columns(cursor) -> None:
    _ensure_columns(
        cursor,
        "dut",
        {
            "project_id": "INT NOT NULL",
            "sn": "VARCHAR(255)",
            "connect_type": "VARCHAR(64)",
            "mac_address": "VARCHAR(64)",
            "device_number": "VARCHAR(128)",
            "ip": "VARCHAR(128)",
            "software_version": "VARCHAR(128)",
            "driver_version": "VARCHAR(128)",
            "android_version": "VARCHAR(64)",
            "kernel_version": "VARCHAR(64)",
            "hw_phase": "VARCHAR(64)",
            "wifi_module_sn": "VARCHAR(128)",
            "antenna": "VARCHAR(128)",
            "payload_json": "JSON",
        },
    )


def _ensure_performance_columns(cursor) -> None:
    _ensure_columns(
        cursor,
        "performance",
        {
            "test_report_id": "INT NOT NULL",
            "execution_id": "INT NOT NULL",
            "report_name": "VARCHAR(255) NOT NULL",
        },
    )


def _ensure_perf_metric_kv_columns(cursor) -> None:
    _ensure_columns(
        cursor,
        "perf_metric_kv",
        {
            "execution_id": "INT NOT NULL",
            "metric_name": "VARCHAR(64) NOT NULL",
            "metric_unit": "VARCHAR(16)",
            "metric_value": "DECIMAL(12,4) NOT NULL",
            "stage": "VARCHAR(64)",
        },
    )


def _ensure_grants(
    *,
    config: Mapping[str, object],
    target_db: str,
    grant_user: str,
    grant_password: str,
) -> None:
    admin_conn = pymysql.connect(
        host=str(config["host"]),
        port=int(config.get("port", 3306)),
        user=str(config["user"]),
        password=str(config["password"]),
        charset=config.get("charset", "utf8mb4"),
        autocommit=True,
        cursorclass=DictCursor,
    )
    try:
        with admin_conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{target_db}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(
                "CREATE USER IF NOT EXISTS %s@'%%' IDENTIFIED BY %s",
                (grant_user, grant_password),
            )
            cursor.execute(
                f"GRANT ALL PRIVILEGES ON `{target_db}`.* TO %s@'%%'",
                (grant_user,),
            )
            cursor.execute("FLUSH PRIVILEGES")
    finally:
        admin_conn.close()


def _distinct_values(
    cursor,
    *,
    table: str,
    column: str,
    limit: int,
) -> List[object]:
    cursor.execute(
        f"SELECT v FROM ("
        f"  SELECT `{column}` AS v, MAX(id) AS max_id "
        f"  FROM `{table}` "
        f"  WHERE `{column}` IS NOT NULL AND `{column}` <> '' "
        f"  GROUP BY `{column}` "
        f"  ORDER BY max_id DESC "
        f"  LIMIT {int(limit)}"
        f") AS t ORDER BY max_id DESC"
    )
    return [row["v"] for row in cursor.fetchall()]


def _build_value_pools(
    *,
    source_cursor,
) -> dict[str, List[object]]:
    pools: dict[str, List[object]] = {}

    pools["project.customer"] = _distinct_values(source_cursor, table="project", column="customer", limit=200)
    pools["project.project_type"] = _distinct_values(source_cursor, table="project", column="project_type", limit=200)
    pools["project.soc"] = _distinct_values(source_cursor, table="project", column="soc", limit=200)
    pools["project.wifi_module"] = _distinct_values(source_cursor, table="project", column="wifi_module", limit=200)
    pools["project.interface"] = _distinct_values(source_cursor, table="project", column="interface", limit=200)
    pools["project.ecosystem"] = _distinct_values(source_cursor, table="project", column="ecosystem", limit=200)

    pools["router.brand"] = _distinct_values(source_cursor, table="router", column="brand", limit=200)
    pools["router.model"] = _distinct_values(source_cursor, table="router", column="model", limit=500)

    pools["dut.connect_type"] = _distinct_values(source_cursor, table="dut", column="connect_type", limit=50)
    pools["dut.software_version"] = _distinct_values(source_cursor, table="dut", column="software_version", limit=500)
    pools["dut.driver_version"] = _distinct_values(source_cursor, table="dut", column="driver_version", limit=500)
    pools["dut.android_version"] = _distinct_values(source_cursor, table="dut", column="android_version", limit=50)
    pools["dut.kernel_version"] = _distinct_values(source_cursor, table="dut", column="kernel_version", limit=200)

    pools["test_case.report_type"] = _distinct_values(source_cursor, table="test_report", column="report_type", limit=50)

    pools["test_run.run_type"] = _distinct_values(source_cursor, table="execution", column="run_type", limit=50)
    pools["test_run.run_source"] = _distinct_values(source_cursor, table="execution", column="run_source", limit=50)
    pools["test_run.ap_name"] = _distinct_values(source_cursor, table="lab_environment", column="ap_name", limit=200)
    pools["test_run.bt_mode"] = _distinct_values(source_cursor, table="execution", column="bt_mode", limit=50)

    pools["compat.ap_brand"] = _distinct_values(source_cursor, table="compatibility", column="ap_brand", limit=200)
    pools["compat.band"] = _distinct_values(source_cursor, table="compatibility", column="band", limit=10)
    pools["compat.wifi_mode"] = _distinct_values(source_cursor, table="compatibility", column="wifi_mode", limit=50)
    pools["compat.bandwidth"] = _distinct_values(source_cursor, table="compatibility", column="bandwidth", limit=50)
    pools["compat.security"] = _distinct_values(source_cursor, table="compatibility", column="security", limit=50)
    pools["compat.scan_result"] = _distinct_values(source_cursor, table="compatibility", column="scan_result", limit=10)
    pools["compat.connect_result"] = _distinct_values(source_cursor, table="compatibility", column="connect_result", limit=10)
    pools["compat.tx_result"] = _distinct_values(source_cursor, table="compatibility", column="tx_result", limit=10)
    pools["compat.rx_result"] = _distinct_values(source_cursor, table="compatibility", column="rx_result", limit=10)

    pools["kv.metric_name"] = _distinct_values(source_cursor, table="perf_metric_kv", column="metric_name", limit=200)
    pools["kv.metric_unit"] = _distinct_values(source_cursor, table="perf_metric_kv", column="metric_unit", limit=50)
    pools["kv.stage"] = _distinct_values(source_cursor, table="perf_metric_kv", column="stage", limit=50)

    return pools


def _pick(pool: Sequence[object], fallback: Sequence[object]) -> object:
    if pool:
        return random.choice(pool)
    return random.choice(fallback)


def _remove_seeded_data(
    cursor,
    *,
    seed_namespace: str,
    project_ids: Sequence[int],
    purge_legacy: bool,
) -> None:
    if purge_legacy:
        cursor.execute(
            f"SELECT id FROM `test_report` "
            f"WHERE `project_id` IN ({', '.join(['%s'] * len(project_ids))}) "
            f"  AND ("
            f"    `notes`=%s "
            f"    OR `report_name` LIKE 'performance\\_%%' "
            f"    OR `report_name` LIKE 'compatibility\\_%%' "
            f"    OR `report_name` LIKE 'other\\_%%' "
            f"    OR `case_path` LIKE 'cases/performance\\_%%' "
            f"    OR `case_path` LIKE 'cases/compatibility\\_%%' "
            f"    OR `case_path` LIKE 'cases/other\\_%%'"
            f"  )",
            (*[int(project_id) for project_id in project_ids], seed_namespace),
        )
    else:
        cursor.execute(
            f"SELECT id FROM `test_report` WHERE `notes`=%s AND `project_id` IN ({', '.join(['%s'] * len(project_ids))})",
            (seed_namespace, *[int(project_id) for project_id in project_ids]),
        )
    report_ids = [int(row["id"]) for row in cursor.fetchall()]
    if not report_ids:
        if purge_legacy:
            cursor.execute("DELETE FROM `execution` WHERE `run_source` = 'dbg'")
            cursor.execute("DELETE FROM `performance` WHERE `report_name` LIKE 'dbg\\_%%'")
            cursor.execute("DELETE FROM `dut` WHERE `sn` LIKE 'SN-%'")
        else:
            cursor.execute("DELETE FROM `dut` WHERE `sn` LIKE %s", (f"SN-{seed_namespace}-%",))
        return

    cursor.execute(
        f"SELECT id FROM `execution` WHERE `test_report_id` IN ({', '.join(['%s'] * len(report_ids))})",
        tuple(report_ids),
    )
    execution_ids = [int(row["id"]) for row in cursor.fetchall()]

    if execution_ids:
        in_clause = ", ".join(["%s"] * len(execution_ids))
        cursor.execute(f"DELETE FROM `compatibility` WHERE `execution_id` IN ({in_clause})", tuple(execution_ids))
        cursor.execute(f"DELETE FROM `perf_metric_kv` WHERE `execution_id` IN ({in_clause})", tuple(execution_ids))
        cursor.execute(f"DELETE FROM `performance` WHERE `execution_id` IN ({in_clause})", tuple(execution_ids))

    cursor.execute(
        f"DELETE FROM `artifact` WHERE `test_report_id` IN ({', '.join(['%s'] * len(report_ids))})",
        tuple(report_ids),
    )
    cursor.execute(
        f"DELETE FROM `execution` WHERE `test_report_id` IN ({', '.join(['%s'] * len(report_ids))})",
        tuple(report_ids),
    )
    cursor.execute(
        f"DELETE FROM `test_report` WHERE `id` IN ({', '.join(['%s'] * len(report_ids))})",
        tuple(report_ids),
    )
    cursor.execute("DELETE FROM `dut` WHERE `sn` LIKE %s", (f"SN-{seed_namespace}-%",))


def _randomize_audit_timestamps(
    cursor,
    *,
    table: str,
    id_column: str,
    ids: Sequence[int],
    days_back: int = 365,
) -> None:
    if not ids:
        return
    rows: List[Sequence[object]] = []
    for row_id in ids:
        created_at = _random_utc_datetime(days_back=days_back)
        updated_at = created_at + timedelta(seconds=random.randint(0, 7 * 24 * 3600))
        rows.append((created_at, updated_at, int(row_id)))
    cursor.executemany(
        f"UPDATE `{table}` SET `created_at`=%s, `updated_at`=%s WHERE `{id_column}`=%s",
        rows,
    )


def seed_wifi_debug(
    *,
    plan: SeedPlan,
    target_db: str,
    source_db: str,
    grant_user: str,
    grant_password: str,
    seed_namespace: str,
    purge_legacy: bool,
    seed: int | None = None,
) -> None:
    if seed is not None:
        random.seed(seed)

    run_tag = _utc_run_tag()
    run_token = f"{run_tag}_{random.randint(1000, 9999)}"

    config = load_mysql_config()
    print(f"MySQL endpoint: {config.get('host')}:{config.get('port', 3306)} user={config.get('user')}")
    source_connection = _connect_database(config, database=source_db, autocommit=True)
    try:
        with source_connection.cursor() as source_cursor:
            source_cursor.execute("SELECT @@hostname AS host, @@port AS port, DATABASE() AS db")
            info = source_cursor.fetchone() or {}
            print(f"MySQL server: {info.get('host')}:{info.get('port')} source_db={info.get('db')}")
            pools = _build_value_pools(source_cursor=source_cursor)
    finally:
        source_connection.close()

    _ensure_grants(
        config=config,
        target_db=target_db,
        grant_user=grant_user,
        grant_password=grant_password,
    )

    connection = _connect_database(config, database=target_db, autocommit=False)
    try:
        print(f"Target database: {target_db}")
        ensure_report_tables(_ConnectionClient(connection))
        connection.commit()
        schema_dir = PROJECT_ROOT / "temp" / "mysql_schema"
        schema_dir.mkdir(parents=True, exist_ok=True)
        schema_path = schema_dir / f"{target_db}_schema.md"
        schema_path.write_text(
            render_schema_markdown(get_schema_catalog()),
            encoding="utf-8",
        )
        print(f"Schema detail written: {schema_path}")
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@hostname AS host, @@port AS port, DATABASE() AS db")
            info = cursor.fetchone() or {}
            print(f"MySQL server: {info.get('host')}:{info.get('port')} target_db={info.get('db')}")
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
        print(f"Tables after ensure_report_tables: {len(tables)}")

        with connection.cursor() as cursor:
            projects = _load_projects(cursor)
            router_ids = _load_router_ids(cursor)
            lab_ids = _load_lab_ids(cursor)
            if not projects:
                raise RuntimeError("project table is empty; run init sync before seeding.")
            if not router_ids:
                raise RuntimeError("router table is empty; run init sync before seeding.")
            if not lab_ids:
                raise RuntimeError("lab table is empty; run init sync before seeding.")
            project_ids = [int(project.id) for project in projects]
            _remove_seeded_data(
                cursor,
                seed_namespace=seed_namespace,
                project_ids=project_ids,
                purge_legacy=purge_legacy,
            )

            case_pairs, perf_case_types, compat_case_ids = _seed_test_cases(
                cursor,
                plan,
                seed_namespace=seed_namespace,
                run_token=run_token,
                projects=projects,
                pools=pools,
            )
            duts_by_project_id = _seed_duts(cursor, plan, seed_namespace, run_token, projects, pools)
            run_ids = _seed_test_runs(cursor, plan, seed_namespace, run_token, case_pairs, duts_by_project_id, lab_ids, pools)

            cursor.execute(
                "SELECT id, test_report_id FROM `execution` WHERE `run_source` = 'dbg' ORDER BY id ASC"
            )
            run_ids_by_case: dict[int, List[int]] = {}
            for row in cursor.fetchall():
                run_ids_by_case.setdefault(int(row["test_report_id"]), []).append(int(row["id"]))

            compat_run_ids: List[int] = []
            for case_id in compat_case_ids:
                compat_run_ids.extend(run_ids_by_case.get(case_id, []))

            _seed_performance(cursor, plan, seed_namespace, run_token, perf_case_types, run_ids_by_case)
            _seed_perf_metric_kv(cursor, plan, seed_namespace, run_token, run_ids, pools)
            _seed_compatibility(cursor, plan, seed_namespace, run_token, compat_run_ids, router_ids, pools)

            _randomize_audit_timestamps(
                cursor,
                table="test_report",
                id_column="id",
                ids=[case_id for case_id, _project_id in case_pairs],
            )
            _randomize_audit_timestamps(
                cursor,
                table="execution",
                id_column="id",
                ids=run_ids,
            )

        connection.commit()
    finally:
        connection.close()


class _ConnectionClient:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql: str, args: Tuple[object, ...] | None = None) -> int:
        with self._connection.cursor() as cursor:
            return cursor.execute(sql, args)

    def query_all(self, sql: str, args: Tuple[object, ...] | None = None):
        with self._connection.cursor() as cursor:
            cursor.execute(sql, args)
            return cursor.fetchall()


def _seed_test_cases(
    cursor,
    plan: SeedPlan,
    *,
    seed_namespace: str,
    run_token: str,
    projects: Sequence[SeededProject],
    pools: Mapping[str, Sequence[object]],
) -> tuple[List[Tuple[int, int]], dict[int, str], List[int]]:
    columns = (
        "project_id",
        "report_name",
        "case_path",
        "is_golden",
        "report_type",
        "golden_group",
        "notes",
        "tester",
    )
    rows: List[Sequence[object]] = []
    perf_case_types: dict[int, str] = {}
    used_names: set[str] = set()
    tester_pool = ("coco", "ling.chen", "yonghua.yan")

    def _next_report_name(prefix: str) -> str:
        while True:
            tag = _random_datetime_tag(days_back=365)
            candidate = f"{prefix}_{tag}"
            if candidate not in used_names:
                used_names.add(candidate)
                return candidate

    for project in projects:
        project_tag = _slug(project.project_name)
        perf_total = max(0, int(plan.perf_reports_per_project))
        compat_total = max(0, int(plan.compat_reports_per_project))
        other_total = max(0, int(plan.other_reports_per_project))

        idx = 0
        perf_variants: List[tuple[str, str, int]] = []
        if perf_total:
            perf_variants.append(("golden", "Peak Throughput", 1))
            perf_variants.append(("rvr", "RVR", 0))
            perf_variants.append(("rvo", "RVO", 0))
            perf_variants.append(("peak", "Peak Throughput", 0))
        perf_variants = perf_variants[:perf_total]

        for perf_key, perf_data_type, is_golden in perf_variants:
            report_name = _next_report_name(f"performance_{project_tag}")
            case_path = f"cases/{report_name}.yaml"
            golden_group = "GOLDEN" if is_golden else perf_key.upper()
            tester = random.choice(tester_pool)
            rows.append((project.id, report_name, case_path, is_golden, "performance", golden_group, seed_namespace, tester))
            idx += 1

        for compat_index in range(compat_total):
            report_name = _next_report_name(f"compatibility_{project_tag}")
            case_path = f"cases/{report_name}.yaml"
            is_golden = 1 if compat_index == 0 else 0
            golden_group = "GOLDEN" if is_golden else f"DBG_{idx:05d}"
            tester = random.choice(tester_pool)
            rows.append((project.id, report_name, case_path, is_golden, "compatibility", golden_group, seed_namespace, tester))
            idx += 1

        for i in range(other_total):
            report_name = _next_report_name(f"other_{project_tag}")
            case_path = f"cases/{report_name}.yaml"
            is_golden = 1 if i == 0 else 0
            golden_group = "GOLDEN" if is_golden else f"DBG_{idx:05d}"
            tester = random.choice(tester_pool)
            rows.append((project.id, report_name, case_path, is_golden, "other", golden_group, seed_namespace, tester))
            idx += 1

    sql = (
        "INSERT INTO `test_report` "
        "(`project_id`, `report_name`, `case_path`, `is_golden`, `report_type`, `golden_group`, `notes`, `tester`) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "`id`=LAST_INSERT_ID(`id`), "
        "`report_name`=VALUES(`report_name`), "
        "`case_path`=VALUES(`case_path`), "
        "`is_golden`=VALUES(`is_golden`), "
        "`notes`=VALUES(`notes`), "
        "`tester`=VALUES(`tester`)"
    )
    for batch in _chunks(rows, 2000):
        cursor.executemany(sql, batch)
    cursor.execute(
        "SELECT id, project_id FROM `test_report` WHERE `notes`=%s ORDER BY id ASC",
        (seed_namespace,),
    )
    case_pairs = [(int(row["id"]), int(row["project_id"])) for row in cursor.fetchall()]

    cursor.execute(
        "SELECT id, report_type, golden_group FROM `test_report` WHERE `notes`=%s ORDER BY id ASC",
        (seed_namespace,),
    )
    compat_case_ids: List[int] = []
    for row in cursor.fetchall():
        case_id = int(row["id"])
        report_type = str(row.get("report_type") or "")
        if report_type == "compatibility":
            compat_case_ids.append(case_id)
        if report_type != "performance":
            continue
        golden_group = str(row.get("golden_group") or "")
        if golden_group.upper() == "RVR":
            perf_case_types[case_id] = "RVR"
        elif golden_group.upper() == "RVO":
            perf_case_types[case_id] = "RVO"
        else:
            perf_case_types[case_id] = "Peak Throughput"

    return case_pairs, perf_case_types, compat_case_ids


def _normalize_test_case_report_types(cursor) -> None:
    cursor.execute(
        "UPDATE `test_report` "
        "SET `report_type` = CASE MOD(`id`, 10) "
        "  WHEN 0 THEN 'compatibility' "
        "  WHEN 1 THEN 'compatibility' "
        "  ELSE 'performance' "
        "END "
        "WHERE `report_name` LIKE 'dbg\\_%' "
        "  AND (`is_golden` IS NULL OR `is_golden` = 0)"
    )
    cursor.execute(
        "UPDATE `test_report` AS tc "
        "JOIN ("
        "  SELECT id, project_id, "
        "         ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY id) AS rn "
        "  FROM `test_report` "
        "  WHERE `report_name` LIKE 'dbg\\_%' "
        "    AND `is_golden` = 1 "
        "    AND `golden_group` = 'GOLDEN'"
        ") AS t ON t.id = tc.id "
        "SET "
        "  tc.report_type = CASE "
        "    WHEN t.rn = 1 THEN 'performance' "
        "    WHEN t.rn = 2 THEN 'compatibility' "
        "    ELSE tc.report_type "
        "  END, "
        "  tc.is_golden = CASE WHEN t.rn IN (1, 2) THEN 1 ELSE 0 END, "
        "  tc.golden_group = CASE "
        "    WHEN t.rn IN (1, 2) THEN 'GOLDEN' "
        "    ELSE CONCAT('DBG_EXTRA_', LPAD(tc.id, 8, '0')) "
        "  END"
    )


def _seed_duts(
    cursor,
    plan: SeedPlan,
    seed_namespace: str,
    run_token: str,
    projects: Sequence[SeededProject],
    pools: Mapping[str, Sequence[object]],
) -> dict[int, List[int]]:
    _ensure_dut_columns(cursor)

    duts_by_project_id: dict[int, List[int]] = {}
    columns = (
        "project_id",
        "sn",
        "connect_type",
        "mac_address",
        "device_number",
        "ip",
        "software_version",
        "driver_version",
        "android_version",
        "kernel_version",
        "hw_phase",
        "wifi_module_sn",
        "antenna",
        "payload_json",
    )
    rows: List[Sequence[object]] = []
    for project in projects:
        dut_count = random.randint(int(plan.duts_min_per_project), int(plan.duts_max_per_project))
        duts_by_project_id[project.id] = []
        for i in range(dut_count):
            serial_number = f"SN-{seed_namespace}-{run_token}-{project.id:06d}-{i:02d}"
            connect_type = str(_pick(pools.get("dut.connect_type", ()), ["adb", "telnet", "ssh"]))
            mac_address = "02:%02x:%02x:%02x:%02x:%02x" % tuple(random.randint(0, 255) for _ in range(5))
            device_number = f"adb-{project.id:06d}-{i:02d}"
            dut_ip = f"192.168.{random.randint(0, 254)}.{random.randint(1, 254)}"
            software_version = str(
                _pick(
                    pools.get("dut.software_version", ()),
                    [f"V{random.randint(1, 9)}.{random.randint(0, 99)}.{random.randint(0, 999)}"],
                )
            )
            driver_version = str(
                _pick(
                    pools.get("dut.driver_version", ()),
                    [f"D{random.randint(1, 9)}.{random.randint(0, 99)}"],
                )
            )
            android_version = str(_pick(pools.get("dut.android_version", ()), ["9", "10", "11", "12", "13"]))
            kernel_version = str(
                _pick(
                    pools.get("dut.kernel_version", ()),
                    [f"{random.randint(4, 6)}.{random.randint(0, 19)}.{random.randint(0, 99)}"],
                )
            )
            hw_phase = str(_pick((), ["EVT", "DVT", "PVT", "MP"]))
            wifi_module_sn = f"WF-{seed_namespace}-{run_token}-{project.id:06d}-{i:02d}"
            antenna = str(_pick((), ["default", "ext", "int"]))
            rows.append(
                (
                    int(project.id),
                    serial_number,
                    connect_type,
                    mac_address,
                    device_number,
                    dut_ip,
                    software_version,
                    driver_version,
                    android_version,
                    kernel_version,
                    hw_phase,
                    wifi_module_sn,
                    antenna,
                    None,
                )
            )

    _insert_many(cursor, "dut", columns, rows)
    cursor.execute(
        "SELECT id, sn FROM `dut` WHERE `sn` LIKE %s ORDER BY id ASC",
        (f"SN-{seed_namespace}-{run_token}-%",),
    )
    for row in cursor.fetchall():
        serial = str(row.get("sn") or "")
        parts = serial.split("-")
        project_id = int(parts[3]) if len(parts) >= 5 else 0
        if project_id in duts_by_project_id:
            duts_by_project_id[project_id].append(int(row["id"]))
    return duts_by_project_id


def _seed_test_runs(
    cursor,
    plan: SeedPlan,
    seed_namespace: str,
    run_token: str,
    case_pairs: Sequence[Tuple[int, int]],
    duts_by_project_id: Mapping[int, Sequence[int]],
    lab_ids: Sequence[int],
    pools: Mapping[str, Sequence[object]],
) -> List[int]:
    columns = (
        "test_report_id",
        "run_type",
        "dut_id",
        "lab_id",
        "bt_mode",
        "bt_ble_alias",
        "bt_classic_alias",
        "run_source",
        "duration_seconds",
        "payload_json",
    )
    rows: List[Sequence[object]] = []
    dut_cursor_by_project: dict[int, int] = {}
    for test_case_id, _project_id in case_pairs:
        for run_index in range(plan.runs_per_case):
            run_type = str(_pick(pools.get("test_run.run_type", ()), ["manual", "ci", "nightly"]))
            project_duts = list(duts_by_project_id[_project_id])
            dut_index = dut_cursor_by_project.get(_project_id, 0) % len(project_duts)
            dut_id = project_duts[dut_index]
            dut_cursor_by_project[_project_id] = dut_index + 1
            ap_name = str(_pick(pools.get("test_run.ap_name", ()), [f"ap-{random.randint(1, 64):02d}"]))
            ap_address = f"172.16.{random.randint(0, 254)}.{random.randint(1, 254)}"
            lab_id = random.choice(list(lab_ids))
            bt_mode = str(_pick(pools.get("test_run.bt_mode", ()), ["off", "ble", "classic", "dual"]))
            bt_ble_alias = f"ble-{random.randint(1, 9999):04d}"
            bt_classic_alias = f"bt-{random.randint(1, 9999):04d}"
            run_source = "dbg"
            duration_seconds = random.randint(5, 3600)
            rows.append(
                (
                    test_case_id,
                    run_type,
                    dut_id,
                    lab_id,
                    bt_mode,
                    bt_ble_alias,
                    bt_classic_alias,
                    run_source,
                    duration_seconds,
                    json.dumps(
                        {"ap_name": ap_name, "ap_address": ap_address},
                        ensure_ascii=True,
                        separators=(",", ":"),
                    ),
                )
            )

    _insert_many(cursor, "execution", columns, rows, chunk_size=1000)
    cursor.execute("SELECT id FROM `execution` ORDER BY id ASC")
    return [int(row["id"]) for row in cursor.fetchall()]


def _seed_performance(
    cursor,
    plan: SeedPlan,
    seed_namespace: str,
    run_token: str,
    performance_case_types: Mapping[int, str],
    run_ids_by_case: Mapping[int, Sequence[int]],
) -> None:
    _ensure_performance_columns(cursor)

    columns = (
        "test_report_id",
        "execution_id",
        "report_name",
        "direction",
        "band",
        "bandwidth_mhz",
        "standard",
        "path_loss_db",
        "rssi",
        "angle_deg",
        "throughput_avg_mbps",
        "throughput_peak_mbps",
    )
    rows: List[Sequence[object]] = []
    for test_case_id, data_type in performance_case_types.items():
        for execution_id in run_ids_by_case.get(test_case_id, ()):
            normalized_type = str(data_type).strip().upper()
            if normalized_type == "RVR":
                attenuation_points = list(range(0, 76, 3))
                for perf_index, attenuation in enumerate(attenuation_points):
                    csv_name = f"dbg_{seed_namespace}_{run_token}_perf_{execution_id:06d}_{perf_index:03d}.csv"
                    throughput_base = 500.0 - (attenuation / 75.0) * 500.0
                    throughput_jitter = random.uniform(5.0, 20.0)
                    if random.choice((True, False)):
                        throughput_avg = throughput_base + throughput_jitter
                    else:
                        throughput_avg = throughput_base - throughput_jitter
                    throughput_avg = max(0.0, round(throughput_avg, 2))
                    rssi_base = -20.0 - (attenuation / 75.0) * 40.0
                    rssi_jitter = random.uniform(5.0, 20.0) / 4.0
                    if random.choice((True, False)):
                        rssi = rssi_base + rssi_jitter
                    else:
                        rssi = rssi_base - rssi_jitter
                    rssi = round(min(-20.0, max(-60.0, rssi)), 2)
                    rows.append(
                        (
                            test_case_id,
                            execution_id,
                            csv_name,
                            "RVR",
                            "uplink" if perf_index % 2 == 0 else "downlink",
                            "5",
                            80,
                            "11ax",
                            float(attenuation),
                            rssi,
                            180.0,
                            throughput_avg,
                            None,
                        )
                    )
            elif normalized_type == "RVO":
                angle_points = list(range(0, 361, 45))
                for perf_index, angle in enumerate(angle_points):
                    csv_name = f"dbg_{seed_namespace}_{run_token}_perf_{execution_id:06d}_{perf_index:03d}.csv"
                    throughput_base = 400.0
                    throughput_jitter = random.uniform(5.0, 20.0) + random.uniform(-100.0, 100.0)
                    throughput_avg = round(min(500.0, max(300.0, throughput_base + throughput_jitter)), 2)
                    rows.append(
                        (
                            test_case_id,
                            execution_id,
                            csv_name,
                            "RVO",
                            "uplink" if perf_index % 2 == 0 else "downlink",
                            "5",
                            80,
                            "11ax",
                            0.0,
                            -20.0,
                            float(angle),
                            throughput_avg,
                            None,
                        )
                    )
            else:
                for perf_index in range(plan.perf_rows_per_run):
                    csv_name = f"dbg_{seed_namespace}_{run_token}_perf_{execution_id:06d}_{perf_index:03d}.csv"
                    throughput_base = 400.0
                    throughput_jitter = random.uniform(5.0, 20.0) + random.uniform(-100.0, 100.0)
                    throughput_peak = round(min(500.0, max(300.0, throughput_base + throughput_jitter)), 2)
                    rows.append(
                        (
                            test_case_id,
                            execution_id,
                            csv_name,
                            "Peak Throughput",
                            "uplink" if perf_index % 2 == 0 else "downlink",
                            "5",
                            80,
                            "11ax",
                            0.0,
                            -20.0,
                            180.0,
                            None,
                            throughput_peak,
                        )
                    )

    _insert_many(cursor, "performance", columns, rows, chunk_size=2000)


def _seed_perf_metric_kv(
    cursor,
    plan: SeedPlan,
    seed_namespace: str,
    run_token: str,
    run_ids: Sequence[int],
    pools: Mapping[str, Sequence[object]],
) -> None:
    _ensure_perf_metric_kv_columns(cursor)

    columns = ("execution_id", "metric_name", "metric_unit", "metric_value", "stage")
    rows: List[Sequence[object]] = []
    for execution_id in run_ids:
        required = plan.inject_rvr_rv0
        remaining = plan.kv_rows_per_run
        if required:
            metric_names = [str(item) for item in pools.get("kv.metric_name", ()) if item]
            metric_names_upper = {name.upper(): name for name in metric_names}
            rvr_name = metric_names_upper.get("RVR", "RVR")
            rvo_name = metric_names_upper.get("RVO", metric_names_upper.get("RV0", "RVO"))
            metric_unit = str(_pick(pools.get("kv.metric_unit", ()), ["dBm", "dB", "Mbps", "ms", "%"]))
            stage = str(_pick(pools.get("kv.stage", ()), ["setup", "run", "teardown"]))
            rows.append((execution_id, rvr_name, metric_unit, round(random.uniform(0.1, 999.9), 4), stage))
            rows.append((execution_id, rvo_name, metric_unit, round(random.uniform(0.1, 999.9), 4), stage))
            remaining = max(0, remaining - 2)

        for i in range(plan.kv_rows_per_run):
            if remaining <= 0:
                break
            metric_name = str(_pick(pools.get("kv.metric_name", ()), ["rssi", "snr", "throughput", "latency", "packet_loss"]))
            metric_unit = str(_pick(pools.get("kv.metric_unit", ()), ["dBm", "dB", "Mbps", "ms", "%"]))
            metric_value = round(random.uniform(0.1, 999.9), 4)
            stage = str(_pick(pools.get("kv.stage", ()), ["setup", "run", "teardown"]))
            rows.append((execution_id, metric_name, metric_unit, metric_value, stage))
            remaining -= 1

    _insert_many(cursor, "perf_metric_kv", columns, rows, chunk_size=2000)


def _seed_compatibility(
    cursor,
    plan: SeedPlan,
    seed_namespace: str,
    run_token: str,
    run_ids: Sequence[int],
    router_ids: Sequence[int],
    pools: Mapping[str, Sequence[object]],
) -> None:
    columns = (
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
    )
    rows: List[Sequence[object]] = []
    for execution_id in run_ids:
        for i in range(plan.compat_rows_per_run):
            router_id = random.choice(router_ids) if router_ids else None
            pdu_ip = f"192.0.2.{random.randint(1, 254)}"
            pdu_port = 1 + (i % 8)
            ap_brand = str(_pick(pools.get("compat.ap_brand", ()), ["TP-LINK", "ASUS", "NETGEAR", "Xiaomi", "Huawei"]))
            band = str(_pick(pools.get("compat.band", ()), ["2.4G", "5G", "6G"]))
            ssid = f"dbg_{seed_namespace}_{run_token}_ssid_{random.randint(1, 9999):04d}"
            wifi_mode = str(_pick(pools.get("compat.wifi_mode", ()), ["11n", "11ac", "11ax", "11be"]))
            bandwidth = str(_pick(pools.get("compat.bandwidth", ()), ["20", "40", "80", "160"]))
            security = str(_pick(pools.get("compat.security", ()), ["open", "wpa2", "wpa3", "mixed"]))
            scan_result = str(_pick(pools.get("compat.scan_result", ()), ["pass", "fail"]))
            connect_result = str(_pick(pools.get("compat.connect_result", ()), ["pass", "fail"]))
            tx_result = str(_pick(pools.get("compat.tx_result", ()), ["pass", "fail"]))
            tx_channel = str(random.randint(1, 165))
            tx_rssi_base = random.uniform(-55.0, -25.0)
            tx_rssi_jitter = random.uniform(5.0, 20.0) / 4.0
            tx_rssi_value = tx_rssi_base + tx_rssi_jitter if random.choice((True, False)) else tx_rssi_base - tx_rssi_jitter
            tx_rssi = str(round(min(-20.0, max(-60.0, tx_rssi_value)), 2))
            tx_criteria = random.choice(["ok", "low_rssi", "low_tp"])
            tx_throughput_base = random.uniform(320.0, 480.0)
            tx_throughput_jitter = random.uniform(5.0, 20.0)
            tx_throughput_value = (
                tx_throughput_base + tx_throughput_jitter
                if random.choice((True, False))
                else tx_throughput_base - tx_throughput_jitter
            )
            tx_throughput_mbps = str(round(min(500.0, max(300.0, tx_throughput_value)), 2))
            rx_result = str(_pick(pools.get("compat.rx_result", ()), ["pass", "fail"]))
            rx_channel = str(random.randint(1, 165))
            rx_rssi_base = random.uniform(-55.0, -25.0)
            rx_rssi_jitter = random.uniform(5.0, 20.0) / 4.0
            rx_rssi_value = rx_rssi_base + rx_rssi_jitter if random.choice((True, False)) else rx_rssi_base - rx_rssi_jitter
            rx_rssi = str(round(min(-20.0, max(-60.0, rx_rssi_value)), 2))
            rx_criteria = random.choice(["ok", "low_rssi", "low_tp"])
            rx_throughput_base = random.uniform(320.0, 480.0)
            rx_throughput_jitter = random.uniform(5.0, 20.0)
            rx_throughput_value = (
                rx_throughput_base + rx_throughput_jitter
                if random.choice((True, False))
                else rx_throughput_base - rx_throughput_jitter
            )
            rx_throughput_mbps = str(round(min(500.0, max(300.0, rx_throughput_value)), 2))
            rows.append(
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
                    tx_throughput_mbps,
                    rx_result,
                    rx_channel,
                    rx_rssi,
                    rx_criteria,
                    rx_throughput_mbps,
                )
            )

    _insert_many(cursor, "compatibility", columns, rows, chunk_size=2000)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and seed wifi_debug database with synthetic data.")
    parser.add_argument("--target-db", type=str, default="wifi_debug")
    parser.add_argument("--source-db", type=str, default="wifi_test")
    parser.add_argument("--grant-user", type=str, default=None)
    parser.add_argument("--grant-password", type=str, default=None)
    parser.add_argument("--seed-namespace", type=str, default="wifi_debug_seed")
    parser.add_argument("--purge-legacy", action="store_true", default=True)
    parser.add_argument("--no-purge-legacy", dest="purge_legacy", action="store_false")
    parser.add_argument("--runs-per-case", type=int, default=5)
    parser.add_argument("--perf-reports-per-project", type=int, default=4)
    parser.add_argument("--compat-reports-per-project", type=int, default=2)
    parser.add_argument("--other-reports-per-project", type=int, default=0)
    parser.add_argument("--perf-rows-per-run", type=int, default=1)
    parser.add_argument("--kv-rows-per-run", type=int, default=5)
    parser.add_argument("--compat-rows-per-run", type=int, default=1)
    parser.add_argument("--inject-rvr-rv0", action="store_true", default=True)
    parser.add_argument("--no-inject-rvr-rv0", dest="inject_rvr_rv0", action="store_false")
    parser.add_argument("--seed", type=int, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    base = load_mysql_config()
    grant_user = str(args.grant_user or base["user"])
    grant_password = str(args.grant_password or base["password"])
    plan = SeedPlan(
        runs_per_case=args.runs_per_case,
        perf_reports_per_project=args.perf_reports_per_project,
        compat_reports_per_project=args.compat_reports_per_project,
        other_reports_per_project=args.other_reports_per_project,
        perf_rows_per_run=args.perf_rows_per_run,
        kv_rows_per_run=args.kv_rows_per_run,
        compat_rows_per_run=args.compat_rows_per_run,
        golden_perf_reports_per_project=1,
        duts_min_per_project=3,
        duts_max_per_project=5,
        inject_rvr_rv0=bool(args.inject_rvr_rv0),
    )
    seed_wifi_debug(
        plan=plan,
        target_db=str(args.target_db),
        source_db=str(args.source_db),
        grant_user=grant_user,
        grant_password=grant_password,
        seed_namespace=str(args.seed_namespace),
        purge_legacy=bool(args.purge_legacy),
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
