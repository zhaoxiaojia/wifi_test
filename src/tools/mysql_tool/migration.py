from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.tools.mysql_tool.client import MySqlClient
from src.tools.mysql_tool.schema import ensure_report_tables, ensure_table, get_table_spec


_TARGET_TABLES: tuple[str, ...] = (
    "project",
    "test_report",
    "dut",
    "lab",
    "lab_environment",
    "execution",
    "router",
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
        "SELECT `id` FROM `project` WHERE `brand`=%s AND `product_line`=%s AND `nickname`=%s LIMIT 1",
        ("__legacy__", "__legacy__", "__legacy__"),
    )
    if row and row.get("id") is not None:
        return int(row["id"])

    cols = set(_list_columns(client, table="project"))
    if "payload_json" in cols:
        sql = (
            "INSERT INTO `project` "
            "(`brand`, `product_line`, `nickname`, `project_name`, `project_id`, `payload_json`) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        args = (
            "__legacy__",
            "__legacy__",
            "__legacy__",
            "Legacy Orphans",
            None,
            '{"source":"migration"}',
        )
    else:
        sql = (
            "INSERT INTO `project` "
            "(`brand`, `product_line`, `nickname`, `project_name`, `project_id`) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        args = (
            "__legacy__",
            "__legacy__",
            "__legacy__",
            "Legacy Orphans",
            None,
        )
    return int(client.insert(sql, args))


def _ensure_placeholder_test_report(client: MySqlClient, *, desired_id: int | None) -> int:
    legacy_project_id = _ensure_legacy_project_id(client)
    cols = set(_list_columns(client, table="test_report"))
    has_payload = "payload_json" in cols

    if desired_id is not None and desired_id > 0:
        exists = client.query_one("SELECT COUNT(*) AS cnt FROM `test_report` WHERE `id`=%s", (desired_id,))
        if int(exists["cnt"]) > 0:
            return desired_id

    name = f"legacy_orphan_{desired_id}" if desired_id else "legacy_orphan_auto"
    if has_payload:
        sql = (
            "INSERT INTO `test_report` "
            + ("(`id`, " if desired_id else "(")
            + "`project_id`, `report_name`, `case_path`, `is_golden`, `report_type`, `golden_group`, "
            "`notes`, `tester`, `csv_name`, `csv_path`, `payload_json`) "
            + ("VALUES (%s, " if desired_id else "VALUES (")
            + "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        args: tuple[Any, ...] = (
            *((desired_id,) if desired_id else ()),
            legacy_project_id,
            name,
            None,
            0,
            None,
            None,
            "Auto-created by migration.",
            None,
            None,
            None,
            '{"source":"migration"}',
        )
    else:
        sql = (
            "INSERT INTO `test_report` "
            + ("(`id`, " if desired_id else "(")
            + "`project_id`, `report_name`, `case_path`, `is_golden`, `report_type`, `golden_group`, "
            "`notes`, `tester`, `csv_name`, `csv_path`) "
            + ("VALUES (%s, " if desired_id else "VALUES (")
            + "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        args = (
            *((desired_id,) if desired_id else ()),
            legacy_project_id,
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

        for table in _TARGET_TABLES:
            spec = get_table_spec(table)
            fk_defs = [c.definition for c in spec.constraints if "FOREIGN KEY" in c.definition.upper()]
            _ensure_fk_ref_integrity(client, table=table, constraint_defs=fk_defs)

        changes = _drop_redundancy_against_target(client)
        print(f"[MIGRATION] converge round={round_idx+1} dropped_items={changes}", flush=True)

        print(f"[MIGRATION] ensure_report_tables round={round_idx+1} start", flush=True)
        ensure_report_tables(client)
        print(f"[MIGRATION] ensure_report_tables round={round_idx+1} done", flush=True)

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
