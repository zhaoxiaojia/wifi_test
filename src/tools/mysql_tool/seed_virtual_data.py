"""本地执行的虚拟数据注入脚本。

该脚本直接复用框架中的 MySQL 工具模块，能够自动感知表结构变更并填充
测试所需的虚拟数据。默认注入数量如下：

* ``dut`` 表 20 条
* ``execution`` 表 10 条
* ``performance`` 表 100000 条

可以通过命令行参数调整数量或在注入前清空相关表。
"""

from __future__ import annotations

import argparse
import itertools
import logging
import math
import random
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Sequence

if __package__ is None or __package__ == "":  # 当作脚本直接运行时补充项目根路径
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    PROJECT_ROOT_STR = str(PROJECT_ROOT)
    if PROJECT_ROOT_STR not in sys.path:
        sys.path.insert(0, PROJECT_ROOT_STR)

from src.tools.mysql_tool import MySqlClient
from src.tools.mysql_tool.schema import ensure_report_tables, get_table_spec
from src.tools.mysql_tool.sql_writer import SqlWriter


LOGGER = logging.getLogger("virtual_data_injector")

ENUM_PATTERN = re.compile(r"ENUM\((?P<options>.+)\)", re.IGNORECASE)
DECIMAL_PATTERN = re.compile(r"DECIMAL\(\s*(\d+)\s*,\s*(\d+)\s*\)", re.IGNORECASE)


@dataclass(frozen=True)
class ColumnSpec:
    """
    Column spec.

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
    definition: str


def _build_column_specs(table: str) -> Sequence[ColumnSpec]:
    """
    Build column specs.

    Parameters
    ----------
    table : Any
        Name of the table in the database.

    Returns
    -------
    Sequence[ColumnSpec]
        A value of type ``Sequence[ColumnSpec]``.
    """
    spec = get_table_spec(table)
    return tuple(ColumnSpec(col.name, col.definition) for col in spec.columns)


def _parse_enum_options(definition: str) -> Sequence[str] | None:
    """
    Parse enum options.

    Parameters
    ----------
    definition : Any
        Column definition string from the table specification.

    Returns
    -------
    Sequence[str] | None
        A value of type ``Sequence[str] | None``.
    """
    match = ENUM_PATTERN.search(definition)
    if not match:
        return None
    raw = match.group("options")
    options: List[str] = []
    for part in raw.split(","):
        cleaned = part.strip().strip("'")
        if cleaned:
            options.append(cleaned)
    return options


def _guess_decimal_places(definition: str) -> int:
    """
    Guess decimal places.

    Parameters
    ----------
    definition : Any
        Column definition string from the table specification.

    Returns
    -------
    int
        A value of type ``int``.
    """
    match = DECIMAL_PATTERN.search(definition)
    if not match:
        return 2
    return int(match.group(2))


def _generate_value(
    column: ColumnSpec,
    index: int,
    rng: random.Random,
    *,
    enum_overrides: Mapping[str, Sequence[str]] | None = None,
    numeric_base: float | None = None,
) -> object:
    """
    Generate value.

    Generates random values for seeding or testing purposes.

    Parameters
    ----------
    column : Any
        Column specification object.
    index : Any
        Index of the current row or item in iteration.
    rng : Any
        Random number generator instance.

    Returns
    -------
    object
        A value of type ``object``.
    """
    definition_upper = column.definition.upper()
    enum_candidates = None
    if enum_overrides and column.name in enum_overrides:
        enum_candidates = enum_overrides[column.name]
    if enum_candidates is None:
        enum_candidates = _parse_enum_options(definition_upper)
    if enum_candidates:
        return rng.choice(tuple(enum_candidates))

    if "INT" in definition_upper:
        if numeric_base is not None:
            base_value = numeric_base
        else:
            base_value = index + 1
        return int(base_value)

    if "DECIMAL" in definition_upper:
        decimals = _guess_decimal_places(definition_upper)
        span = numeric_base if numeric_base is not None else 100.0
        value = rng.uniform(0.0, float(span) or 1.0)
        return round(value, decimals)

    if "FLOAT" in definition_upper or "DOUBLE" in definition_upper:
        span = numeric_base if numeric_base is not None else 100.0
        return round(rng.uniform(0.0, float(span) or 1.0), 3)

    return f"{column.name}_{index:05d}"


def _build_packet_loss_summary(rng: random.Random) -> str:
    """
    Build packet loss summary.

    Generates random values for seeding or testing purposes.

    Parameters
    ----------
    rng : Any
        Random number generator instance.

    Returns
    -------
    str
        A value of type ``str``.
    """
    total = rng.randint(1000, 50000)
    lost = rng.randint(0, max(1, total // 20))
    loss_pct = (lost / total * 100.0) if total else 0.0
    return f"{lost}/{total}({loss_pct:.2f}%)"


def _truncate_tables(client: MySqlClient, tables: Sequence[str]) -> None:
    """
    Truncate tables.

    Runs an SQL statement using a database cursor.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    tables : Any
        The ``tables`` parameter.

    Returns
    -------
    None
        This function does not return a value.
    """
    LOGGER.info("Truncating tables: %s", ", ".join(tables))
    client.execute("SET FOREIGN_KEY_CHECKS=0")
    try:
        for table in tables:
            client.execute(f"TRUNCATE TABLE `{table}`")
    finally:
        client.execute("SET FOREIGN_KEY_CHECKS=1")


def _insert_with_ids(
    client: MySqlClient,
    table: str,
    columns: Sequence[ColumnSpec],
    rows: Iterable[Sequence[object]],
) -> List[int]:
    """
    Insert with ids.

    Inserts rows into the database and returns the last inserted ID.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    table : Any
        Name of the table in the database.
    columns : Any
        Sequence of column specifications.
    rows : Any
        Iterable or sequence of data rows.

    Returns
    -------
    List[int]
        A value of type ``List[int]``.
    """
    writer = SqlWriter(table)
    sql = writer.insert_statement([column.name for column in columns])
    inserted_ids: List[int] = []
    for row in rows:
        inserted_id = client.insert(sql, tuple(row))
        inserted_ids.append(inserted_id)
    LOGGER.info("Inserted %d rows into %s", len(inserted_ids), table)
    return inserted_ids


def _chunked(rows: Iterable[Sequence[object]], *, chunk_size: int) -> Iterator[List[Sequence[object]]]:
    """
    Chunked.

    Parameters
    ----------
    rows : Any
        Iterable or sequence of data rows.

    Returns
    -------
    Iterator[List[Sequence[object]]]
        A value of type ``Iterator[List[Sequence[object]]]``.
    """
    chunk: List[Sequence[object]] = []
    for row in rows:
        chunk.append(row)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _insert_bulk(
    client: MySqlClient,
    table: str,
    columns: Sequence[ColumnSpec],
    rows: Iterable[Sequence[object]],
    *,
    chunk_size: int = 1000,
) -> int:
    """
    Insert bulk.

    Executes multiple SQL statements in a batch using a cursor.

    Parameters
    ----------
    client : Any
        An instance of MySqlClient used to interact with the database.
    table : Any
        Name of the table in the database.
    columns : Any
        Sequence of column specifications.
    rows : Any
        Iterable or sequence of data rows.

    Returns
    -------
    int
        A value of type ``int``.
    """
    writer = SqlWriter(table)
    sql = writer.insert_statement([column.name for column in columns])
    affected = 0
    for chunk in _chunked(rows, chunk_size=chunk_size):
        affected += client.executemany(sql, chunk)
    LOGGER.info("Inserted %d rows into %s", affected, table)
    return affected


def _generate_dut_rows(count: int, rng: random.Random) -> Sequence[Sequence[object]]:
    """
    Generate dut rows.

    Generates random values for seeding or testing purposes.

    Parameters
    ----------
    count : Any
        Number of records to generate or process.
    rng : Any
        Random number generator instance.

    Returns
    -------
    Sequence[Sequence[object]]
        A value of type ``Sequence[Sequence[object]]``.
    """
    columns = _build_column_specs("dut")
    version_map = {
        "software_version": ["Sahara", "Mirage", "Aurora"],
        "driver_version": ["5.10", "6.3", "7.1"],
        "hardware_version": ["EVT", "DVT", "PVT"],
        "android_version": ["Android 13", "Android 14", "Android 15"],
        "kernel_version": ["5.10", "5.15", "6.1"],
    }

    rows: List[List[object]] = []
    for index in range(count):
        values: List[object] = []
        for column in columns:
            if column.name in version_map:
                values.append(rng.choice(version_map[column.name]))
                continue
            if column.name == "connect_type":
                values.append(rng.choice(["USB", "PCIe", "SDIO"]))
                continue
            if column.name == "adb_device":
                values.append(f"device-{1000 + index}")
                continue
            if column.name == "telnet_ip":
                values.append(f"192.168.{index // 16}.{index % 255}")
                continue
            if column.name == "product_line":
                values.append(rng.choice(["Pixel", "Nexus", "Xperia"]))
                continue
            if column.name == "project":
                values.append(f"Project-{index:02d}")
                continue
            if column.name == "main_chip":
                values.append(rng.choice(["Qualcomm", "MediaTek", "Broadcom"]))
                continue
            if column.name == "wifi_module":
                values.append(rng.choice(["QCN9024", "BCM4375", "MT7925"]))
                continue
            if column.name == "interface":
                values.append(rng.choice(["WLAN0", "WLAN1"]))
                continue
            values.append(_generate_value(column, index, rng))
        rows.append(values)
    return rows


def _generate_execution_rows(count: int, rng: random.Random) -> Sequence[Sequence[object]]:
    """
    Generate execution rows.

    Generates random values for seeding or testing purposes.

    Parameters
    ----------
    count : Any
        Number of records to generate or process.
    rng : Any
        Random number generator instance.

    Returns
    -------
    Sequence[Sequence[object]]
        A value of type ``Sequence[Sequence[object]]``.
    """
    columns = _build_column_specs("execution")
    rf_models = ["Spirent E6", "Octoscope", "R&S CMW" ]
    corner_models = ["Corner-A", "Corner-B", "Corner-C"]
    lab_names = ["Lab-North", "Lab-East", "Lab-West"]

    rows: List[List[object]] = []
    for index in range(count):
        values: List[object] = []
        for column in columns:
            if column.name == "case_path":
                values.append(f"test/performance/case_{index:03d}.py")
                continue
            if column.name == "case_root":
                values.append("test/performance")
                continue
            if column.name == "router_name":
                values.append(rng.choice(["AXE3000", "AX6000", "AX11000"]))
                continue
            if column.name == "router_address":
                values.append(f"10.0.{index // 16}.{index % 255}")
                continue
            if column.name == "rf_model":
                values.append(rng.choice(rf_models))
                continue
            if column.name == "corner_model":
                values.append(rng.choice(corner_models))
                continue
            if column.name == "lab_name":
                values.append(rng.choice(lab_names))
                continue
            values.append(_generate_value(column, index, rng))
        rows.append(values)
    return rows


def _generate_test_reports(
    dut_ids: Sequence[int],
    execution_ids: Sequence[int],
    *,
    rng: random.Random,
    min_reports: int,
) -> Sequence[Sequence[object]]:
    """
    Generate test reports.

    Reads data from a CSV file and processes each row.
    Generates random values for seeding or testing purposes.

    Parameters
    ----------
    dut_ids : Any
        The ``dut_ids`` parameter.
    execution_ids : Any
        The ``execution_ids`` parameter.

    Returns
    -------
    Sequence[Sequence[object]]
        A value of type ``Sequence[Sequence[object]]``.
    """
    columns = _build_column_specs("test_report")
    combinations = list(itertools.product(execution_ids, dut_ids))
    rng.shuffle(combinations)
    selected = combinations[: max(min_reports, 1)]
    rows: List[List[object]] = []
    for index, (execution_id, dut_id) in enumerate(selected):
        values: List[object] = []
        for column in columns:
            if column.name == "execution_id":
                values.append(execution_id)
                continue
            if column.name == "dut_id":
                values.append(dut_id)
                continue
            if column.name == "csv_name":
                values.append(f"virtual_report_{index:03d}.csv")
                continue
            if column.name == "csv_path":
                values.append(f"/tmp/virtual_report_{index:03d}.csv")
                continue
            if column.name == "data_type":
                values.append("performance")
                continue
            if column.name == "case_path":
                values.append(f"test/performance/case_{index:03d}.py")
                continue
            values.append(_generate_value(column, index, rng))
        rows.append(values)
    return rows


def _build_performance_row_generators(
    report_ids: Sequence[int],
    rng: random.Random,
) -> Iterator[Mapping[str, object]]:
    """
    Build performance row generators.

    Reads data from a CSV file and processes each row.
    Generates random values for seeding or testing purposes.

    Parameters
    ----------
    report_ids : Any
        The ``report_ids`` parameter.
    rng : Any
        Random number generator instance.

    Returns
    -------
    Iterator[Mapping[str, object]]
        A value of type ``Iterator[Mapping[str, object]]``.
    """
    standards = ["11a", "11n", "11ac", "11ax"]
    bands = ["2.4", "5", "6"]
    bandwidths = [20, 40, 80, 160]
    directions = ["uplink", "downlink", "bi"]
    protocols = ["TCP", "UDP"]
    test_categories = ["RVR", "RVO"]

    base_time = datetime.utcnow() - timedelta(days=3)
    for index in itertools.count():
        yield {
            "test_report_id": rng.choice(report_ids),
            "csv_name": f"virtual_dataset_{index % 500:03d}.csv",
            "data_type": "performance",
            "serial_number": f"SN-{100000 + index:06d}",
            "test_category": rng.choice(test_categories),
            "standard": rng.choice(standards),
            "band": rng.choice(bands),
            "bandwidth_mhz": rng.choice(bandwidths),
            "phy_rate_mbps": round(rng.uniform(50, 2400), 3),
            "center_freq_mhz": rng.choice([2412, 2437, 2462, 5180, 5500, 5805, 5955, 6105]),
            "protocol": rng.choice(protocols),
            "direction": rng.choice(directions),
            "total_path_loss": round(rng.uniform(40, 120), 2),
            "path_loss_db": round(rng.uniform(40, 120), 2),
            "rssi": round(rng.uniform(-85, -30), 2),
            "angle_deg": round(rng.uniform(0, 360), 2),
            "mcs_rate": rng.choice(["MCS7", "MCS9", "MCS11"]),
            "throughput_peak_mbps": round(rng.uniform(100, 2000), 3),
            "throughput_avg_mbps": round(rng.uniform(80, 1500), 3),
            "target_throughput_mbps": round(rng.uniform(100, 1800), 3),
            "latency_ms": round(rng.uniform(0.1, 20.0), 3),
            "packet_loss": _build_packet_loss_summary(rng),
            "created_at": base_time + timedelta(seconds=index * 5),
        }


def _generate_performance_rows(
    count: int,
    report_ids: Sequence[int],
    rng: random.Random,
) -> Iterator[Sequence[object]]:
    """
    Generate performance rows.

    Parameters
    ----------
    count : Any
        Number of records to generate or process.
    report_ids : Any
        The ``report_ids`` parameter.
    rng : Any
        Random number generator instance.

    Returns
    -------
    Iterator[Sequence[object]]
        A value of type ``Iterator[Sequence[object]]``.
    """
    columns = _build_column_specs("performance")
    enum_overrides: Dict[str, Sequence[str]] = {
        "direction": ("uplink", "downlink", "bi"),
    }

    row_iter = _build_performance_row_generators(report_ids, rng)
    for index in range(count):
        payload = next(row_iter)
        values: List[object] = []
        for column in columns:
            if column.name in payload:
                values.append(payload[column.name])
                continue
            values.append(
                _generate_value(
                    column,
                    index,
                    rng,
                    enum_overrides=enum_overrides,
                    numeric_base=payload.get("bandwidth_mhz", 160),
                )
            )
        yield values


def _resolve_min_reports(performance_count: int, dut_count: int, execution_count: int) -> int:
    """
    Resolve min reports.

    Parameters
    ----------
    performance_count : Any
        The ``performance_count`` parameter.
    dut_count : Any
        The ``dut_count`` parameter.
    execution_count : Any
        The ``execution_count`` parameter.

    Returns
    -------
    int
        A value of type ``int``.
    """
    if performance_count <= 0:
        return 0
    candidate = int(math.sqrt(performance_count) // 2)
    candidate = max(candidate, min(dut_count * execution_count, 10))
    return min(candidate, max(1, dut_count * execution_count))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """
    Parse args.

    Defines and configures command-line arguments for the CLI.

    Parameters
    ----------
    argv : Any
        The ``argv`` parameter.

    Returns
    -------
    argparse.Namespace
        A value of type ``argparse.Namespace``.
    """
    parser = argparse.ArgumentParser(description="向数据库注入虚拟数据")
    parser.add_argument("--dut-count", type=int, default=20, help="DUT 表注入数量")
    parser.add_argument("--execution-count", type=int, default=10, help="Execution 表注入数量")
    parser.add_argument(
        "--performance-count", type=int, default=100_000, help="Performance 表注入数量"
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="注入前清空 performance/test_report/execution/dut 表",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=202405,
        help="随机种子，默认为 202405",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="performance 表批量写入的单批数量",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """
    Main.

    Ensures that required tables exist before inserting data.
    Logs informational messages and errors for debugging purposes.
    Generates random values for seeding or testing purposes.

    Parameters
    ----------
    argv : Any
        The ``argv`` parameter.

    Returns
    -------
    None
        This function does not return a value.
    """
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    rng = random.Random(args.seed)

    with MySqlClient() as client:
        ensure_report_tables(client)
        if args.truncate:
            _truncate_tables(client, ("performance", "test_report", "execution", "dut"))

        dut_rows = _generate_dut_rows(args.dut_count, rng)
        dut_ids = _insert_with_ids(client, "dut", _build_column_specs("dut"), dut_rows)

        execution_rows = _generate_execution_rows(args.execution_count, rng)
        execution_ids = _insert_with_ids(
            client, "execution", _build_column_specs("execution"), execution_rows
        )

        min_reports = _resolve_min_reports(args.performance_count, len(dut_ids), len(execution_ids))
        report_rows = _generate_test_reports(
            dut_ids,
            execution_ids,
            rng=rng,
            min_reports=min_reports,
        )
        report_ids = _insert_with_ids(
            client, "test_report", _build_column_specs("test_report"), report_rows
        )

        performance_rows = _generate_performance_rows(args.performance_count, report_ids, rng)
        _insert_bulk(
            client,
            "performance",
            _build_column_specs("performance"),
            performance_rows,
            chunk_size=max(1, args.batch_size),
        )

    LOGGER.info(
        "虚拟数据注入完成：dut=%d execution=%d test_report=%d performance=%d",
        len(dut_rows),
        len(execution_rows),
        len(report_rows),
        args.performance_count,
    )


if __name__ == "__main__":  # pragma: no cover - 手动执行入口
    main()

