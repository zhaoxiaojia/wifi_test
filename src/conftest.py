#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pytest session configuration and hooks for the Wi‑Fi test framework.

This module configures logging, prepares DUT connections (ADB/Telnet),
collects run-time metadata for PyQt UI, and optionally generates
a Wi‑Fi performance report at session end for specific customers.
"""

from __future__ import annotations

import os
import sys
import re
import shutil
from src.tools.connect_tool import command_batch as subprocess
import logging
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Annotated

import pytest
import csv  # noqa: F401  (kept for potential future CSV export)

from src.tools.connect_tool.duts.android import android
from src.tools.connect_tool.duts.linux import linux
from src.tools.connect_tool.duts.onn_dut import onn_dut
from src.tools.connect_tool.duts.roku_dut import roku
from src.tools.connect_tool.transports.serial_tool import serial_tool
from src.tools.connect_tool.transports.telnet_tool import telnet_tool
from src.tools.connect_tool.local_os import LocalOS
from src.tools.performance_result import PerformanceResult
from src.util.constants import load_config
from src.tools.router_tool.Router import Router
from src.tools.reporting import generate_project_report
from src.test.pyqt_log import emit_pyqt_message
from src.test.compatibility.results import write_compatibility_results

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.StreamHandler(sys.stdout)],
        format="%(asctime)s | %(levelname)s | %(filename)s:%(funcName)s(line:%(lineno)d) |  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

# ----------------------------------------------------------------------------
# Globals (Annotated)
# ----------------------------------------------------------------------------

# Accumulated (legacy) per‑test records for optional CSV export. Currently unused
# in favor of TestResult artifacts; kept for backward compatibility.
test_results: Annotated[list, "Accumulated test records (legacy, currently unused)"] = []

# Pattern that replaces characters not in [0‑9A‑Z a‑z . _ -] with "_", then trims
# leading/trailing underscores. Used to build safe filenames.
_FILENAME_SANITIZE_PATTERN: Annotated[re.Pattern[str], "Pattern used to sanitize filename components"] = re.compile(
    r"[^0-9A-Za-z._-]+"
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _find_allure_executable() -> str | None:
    """
    Return the first available Allure CLI executable, or ``None``.

    This helper avoids hard-coding platform-specific names in multiple
    places and keeps Allure integration best-effort only.
    """
    for name in ("allure", "allure.bat", "allure.cmd"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _derive_test_category_from_session(session: pytest.Session) -> Path:
    """
    Derive a logical test category path from the session's collected args.

    The category is the path segment under ``src/test`` for the active
    testcase, for example:
        src/test/performance/test_wifi_rvo.py -> performance/test_wifi_rvo
    When the path cannot be resolved, a generic ``root`` category is used.
    """
    args = getattr(session.config, "args", None) or []
    case_path: Path | None = None
    for raw in args:
        try:
            candidate = Path(raw)
        except TypeError:
            continue
        if candidate.exists():
            case_path = candidate.resolve()
            break
    if case_path is None:
        return Path("root")

    parts = case_path.parts
    category_parts: tuple[str, ...] | None = None
    for idx, part in enumerate(parts):
        if part == "src" and idx + 1 < len(parts) and parts[idx + 1] == "test":
            remaining = parts[idx + 2 :]
            if remaining:
                category_parts = remaining
            break
    if not category_parts:
        # Fallback: use filename (without extension) as the category.
        return Path(case_path.stem)
    # Drop the .py suffix for the last segment while preserving directories.
    *dirs, leaf = category_parts
    leaf_stem = Path(leaf).stem
    if dirs:
        return Path(*dirs) / leaf_stem
    return Path(leaf_stem)


def _generate_allure_report(session: pytest.Session, destination_dir: Path | None) -> None:
    """
    Best-effort Allure report generation with per-category history.

    - Uses ``allure_results`` as the shared result directory (configured via pytest.ini).
    - Derives a history root under ``report/allure_history/<src/test/...>``.
    - Copies history into the results dir before generation and back out
      after generation so that each test category has its own timeline.
    - Places the HTML report under ``destination_dir / 'allure-report'``
      when a result path is configured by the UI controller.
    """
    results_dir = Path("allure_results")
    if not results_dir.exists() or not results_dir.is_dir():
        logging.debug("Allure results directory %s missing; skip Allure report", results_dir)
        return

    allure_exe = _find_allure_executable()
    if allure_exe is None:
        logging.debug("Allure CLI not found on PATH; skip Allure report generation")
        return

    # When running via the UI, ``destination_dir`` is the per-run report dir.
    if destination_dir is None:
        logging.debug("No destination_dir for Allure report; skip HTML generation")
        return

    category_rel = _derive_test_category_from_session(session)
    history_root = Path("report") / "allure_history"
    category_dir = (history_root / category_rel).resolve()

    try:
        category_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        logging.debug("Failed to ensure Allure history directory %s", category_dir, exc_info=True)

    # Inject per-category history into the current results so that Allure
    # can compute trends.
    history_src = category_dir / "history"
    history_dst = results_dir / "history"
    if history_src.exists() and history_src.is_dir():
        try:
            shutil.copytree(history_src, history_dst, dirs_exist_ok=True)
        except Exception:
            logging.debug("Failed to copy Allure history from %s to %s", history_src, history_dst, exc_info=True)

    output_dir = (destination_dir / "allure-report").resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        logging.debug("Failed to ensure Allure output directory %s", output_dir, exc_info=True)

    try:
        cmd = [allure_exe, "generate", str(results_dir.resolve()), "-o", str(output_dir), "--clean"]
        subprocess.run(
            cmd,
            check=True,
        )
    except Exception:
        logging.warning("Allure report generation failed; see debug logs for details", exc_info=True)
        return

    # Persist the refreshed history for this category for the next run.
    history_from_report = output_dir / "history"
    if history_from_report.exists() and history_from_report.is_dir():
        try:
            shutil.copytree(history_from_report, history_src, dirs_exist_ok=True)
        except Exception:
            logging.debug(
                "Failed to update Allure history cache from %s to %s",
                history_from_report,
                history_src,
                exc_info=True,
            )


def _sanitize_filename_component(value) -> str:
    """
    Convert an arbitrary value (e.g., project name) into a safe filename component.

    - Strips surrounding whitespace
    - Replaces disallowed characters with underscore
    - Removes leading/trailing underscores

    Args:
        value: Any value convertible to string.

    Returns:
        str: A sanitized filename‑safe component (may be empty string).
    """
    text = ""
    if value is not None:
        text = str(value).strip()
    if not text:
        return ""
    sanitized = _FILENAME_SANITIZE_PATTERN.sub("_", text)
    return sanitized.strip("_")


def _maybe_generate_project_report() -> None:
    """
    Conditionally generate a Wi‑Fi performance Excel report at session end.

    Behavior:
        - Only runs when pytest.config['project']['customer'] is 'XIAOMI' (case‑insensitive).
        - If a single Wi‑Fi test type was selected (RVR/RVO/PERFORMANCE), force the
          report to that type for clearer labeling.


    Side effects:
        Logs success/failure and exceptions; never raises to the caller.
    """
    config = getattr(pytest, "config", {}) or {}
    fpga_cfg = config.get("project") or {}
    customer = str(fpga_cfg.get("customer", "")).strip().upper()
    if customer != "XIAOMI":
        return

    test_result = getattr(pytest, "testResult", None)
    if test_result is None:
        logging.warning("Skip project report: missing testResult handle")
        return

    selected_types = getattr(pytest, "selected_test_types", set())
    forced_type = None
    if isinstance(selected_types, set) and selected_types:
        if len(selected_types) == 1:
            forced_type = next(iter(selected_types))
            logging.info("Using selected Wi‑Fi test type for project report: %s", forced_type)
        else:
            logging.warning(
                "Multiple Wi‑Fi test types detected (%s); fallback to auto detection.",
                ", ".join(sorted(selected_types)),
            )

    logdir = Path(getattr(test_result, "logdir", "") or ".").resolve()
    result_file = Path(getattr(test_result, "log_file", "") or "")
    software_info = config.get("software_info") or {}
    hardware_info = config.get("hardware_info") or {}

    project_raw = (
        hardware_info.get("project_name")
        or software_info.get("project_name")
        or fpga_cfg.get("project_name")
        or fpga_cfg.get("customer")
        or "Project"
    )
    project_label = _sanitize_filename_component(project_raw) or "Project"
    project_label = "_".join(part.capitalize() for part in project_label.split("_") if part) or "Project"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{project_label}_WiFi_{timestamp}.xlsx"
    output_path = logdir / filename

    try:
        generate_project_report(result_file, output_path, forced_test_type=forced_type)
        logging.info("Generated project Wi‑Fi performance report: %s", output_path)
    except Exception:
        logging.exception("Failed to generate project Wi‑Fi performance report")


# ----------------------------------------------------------------------------
# Pytest hooks
# ----------------------------------------------------------------------------

def pytest_sessionstart(session):
    """
    Framework pre‑action. Runs once per session before test collection.

    - Detects host platform (sets `pytest.win_flag`).
    - Loads global config via `load_config()` and attaches to `pytest.config`.
    - Determines connection type (ADB == 'Android', Telnet == 'Linux') and constructs
      `pytest.dut` accordingly.
    - Initializes optional serial logger when enabled in config.
    - Configures repeat count and result path used by artifacts.

    Args:
        session (pytest.Session): The current pytest session object.
    """
    # Ensure the Allure results directory exists; historical trends are
    # maintained via the dedicated history cache in _generate_allure_report.
    try:
        results_dir = Path("allure_results")
        results_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        logging.debug("Failed to ensure Allure results directory", exc_info=True)

    # get host os
    if ('win32' or 'win64') in sys.platform:
        pytest.win_flag = True
    else:
        pytest.win_flag = False
    pytest.host_os = LocalOS()
    pytest._session_start_ts = time.time()
    # Load configuration (fresh)
    pytest.config = load_config(refresh=True) or {}

    # Connection type setup
    connect_cfg = pytest.config.get("connect_type") or {}
    pytest.connect_type = session.config.getoption("--dut-type") or connect_cfg.get("type")
    pytest.third_party_cfg = connect_cfg.get("third_party", {})

    # Serial (kernel log) setup
    rvr_cfg = pytest.config.get('rvr') or {}
    serial_cfg = pytest.config.get('serial_port') or {}
    serial_cfg["port"] = serial_cfg.get("port", "").split(" (", 1)[0]
    status = serial_cfg.get('status')
    serial_enabled = status
    serial_inst = None
    if serial_enabled:
        serial_inst = serial_tool(
            serial_port=serial_cfg.get('port', ''),
            baud=serial_cfg.get('baud', ''),
            enable_log=True,
        )
        logging.info("Serial logging enabled; kernel_log.txt will be captured.")

    # Repeat times
    repeat_times = int(rvr_cfg.get('repeat', 0) or 0)

    # DUT connection
    match pytest.connect_type:
        case "Android":
            adb_cfg = connect_cfg.get("Android") or {}
            device = session.config.getoption("--android-device") or adb_cfg.get("device") or ""
            project_cfg = pytest.config.get("project") or {}
            customer = session.config.getoption("--project-customer") or project_cfg.get("customer") or ""
            customer = str(customer).strip().upper()
            match customer:
                case "ONN":
                    pytest.dut = onn_dut(serialnumber=device)
                case _:
                    pytest.dut = android(serialnumber=device)
        case "Linux":
            telnet_cfg = connect_cfg.get("Linux") or {}
            telnet_ip = session.config.getoption("--linux-ip") or telnet_cfg.get("ip")
            project_cfg = pytest.config.get("project") or {}
            customer = session.config.getoption("--project-customer") or project_cfg.get("customer") or ""
            customer = str(customer).strip().upper()

            match customer:
                case "ROKU":
                    pytest.dut = roku(telnet_ip, serial=serial_inst)
                case _:
                    pytest.dut = linux(serial=serial_inst, telnet=telnet_tool(telnet_ip))

    if serial_inst is not None:
        pytest.dut.serial = serial_inst

    # Artifact paths and state
    pytest._result_path = session.config.getoption("--resultpath") or os.getcwd()
    pytest._testresult_repeat_times = repeat_times

    # Cleanup temp file used by some legacy scripts
    if os.path.exists('temp.txt'):
        os.remove('temp.txt')


def pytest_addoption(parser):
    """
    Register custom command‑line options for this test framework.

    Args:
        parser (pytest.Parser): Pytest option parser.

    Adds:
        --resultpath: Destination directory for log artifacts (debug.log, kernel.log, etc.).
    """
    parser.addoption("--resultpath", action="store", default=None, help="Test result path")
    parser.addoption("--dut-type", action="store", default=None, help="DUT type: Android or Linux")
    parser.addoption("--android-device", action="store", default=None, help="ADB serial number")
    parser.addoption("--linux-ip", action="store", default=None, help="Linux DUT IP address")
    parser.addoption("--project-customer", action="store", default=None, help="Project customer code (e.g. ROKU)")


def pytest_collection_finish(session):
    """
    After test collection completes:
      - Detect selected Wi‑Fi test types from collected paths.
      - Record total test count for PyQt progress display.

    Args:
        session (pytest.Session): The current pytest session object.
    """
    # For progress, each collected pytest item counts once. Parameterized
    # fixtures are already expanded into individual items, so this total
    # naturally reflects (ip, port, band, test) combinations.
    session.total_test_count = len(session.items)

    # Detect selected test types based on path hints
    selected_types: set[str] = set()
    for item in session.items:
        path_text = str(getattr(item, "fspath", "")).replace("\\", "/").lower()
        if not path_text:
            continue
        if "test/performance/" in path_text:
            selected_types.add("PERFORMANCE")
        if "test_wifi_rvr" in path_text:
            selected_types.add("RVR")
        elif "test_wifi_rvo" in path_text:
            selected_types.add("RVO")
        elif "test/stability/" in path_text:
            selected_types.add("STABILITY")

    if selected_types:
        pytest.selected_test_types = selected_types
        logging.info("Detected selected Wi‑Fi test types: %s", ", ".join(sorted(selected_types)))
    else:
        pytest.selected_test_types = set()


def pytest_runtest_setup(item):
    """
    Called before each test's setup phase.

    Emits a PyQt UI message with the test's original name so the GUI can
    reflect which case is currently running.

    Args:
        item (pytest.Item): The test item about to run.
    """
    emit_pyqt_message("CASE", item.originalname)


def pytest_runtest_logreport(report):
    """
    Called after each phase (setup/call/teardown) of a test item finishes.

    For 'setup' phase, logs parameterized IDs if present to help debugging
    and test case tracing.

    Args:
        report (pytest.TestReport): The report for a specific phase of a test.
    """
    if report.when == "setup" and hasattr(report, "nodeid"):
        test_nodeid = report.nodeid
        if "[" in test_nodeid:
            params = test_nodeid.split("[", 1)[-1].rstrip("]")
            logging.info("Test params: %s", params)


def pytest_collection_modifyitems(config, items):
    """
    Normalize collected test names to display Unicode correctly in console/HTML.

    - Re-encodes names and nodeids using 'unicode-escape' workaround.
    - Prepares for any downstream decorators that inspect `item.function`.

    Args:
        config (pytest.Config): Pytest configuration (unused here).
        items (list[pytest.Item]): Collected test items.
    """
    new_items = []
    for item in items:
        item.name = item.name.encode("utf-8").decode("unicode-escape")
        item._nodeid = item._nodeid.encode("utf-8").decode("unicode-escape")
        func = item.function  # noqa: F841  (placeholder for potential future use)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Augment test reports with PASS/FAIL and return values.

    - On 'setup' failure, mark test_result=FAIL.
    - On 'call', store PASS/FAIL and capture the test's return value (if any)
      into `item._store["return_value"]` for optional reporting.

    Args:
        item (pytest.Item): The test item.
        call (CallInfo): Execution info object provided by pytest.
    """
    outcome = yield
    report = outcome.get_result()

    if report.when == 'setup':
        if report.failed:
            item._store['test_result'] = "FAIL"
    elif report.when == 'call':
        item._store['test_result'] = "PASS" if report.passed else "FAIL" if report.failed else "SKIPP"
        if not report.failed:
            return_value = getattr(call, "result", None) or item._store.get("return_value", None)
            logging.info('record return value: %s', getattr(call, "result", None))
            item._store["return_value"] = return_value


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    """
    After each test's teardown, update the PyQt progress indicator exactly once.

    Args:
        item (pytest.Item): The test item that just finished.
        nextitem (pytest.Item | None): The next item to run (unused).
    """
    yield
    session = item.session
    if not hasattr(session, "pyqt_finished"):
        session.pyqt_finished = 0
    if getattr(item, "_pyqt_progress_recorded", False):
        return
    session.pyqt_finished += 1
    total = getattr(session, "total_test_count", None) or len(session.items)
    emit_pyqt_message("PROGRESS", f" {session.pyqt_finished}/{total}")
    item._pyqt_progress_recorded = True

@pytest.fixture(autouse=True)
def record_test_data(request):
    """
    自动收集测试用例的 fixture 参数 ids,并存储返回值
    """
    test_name = request.node.originalname
    logging.info(test_name)
    fixture_values = {}
    for fixture_name in request.node.fixturenames:
        if fixture_name in request.node.funcargs:
            fixture_values[fixture_name] = request.node.funcargs[fixture_name]

    request.node._store = getattr(request.node, "_store", {})
    request.node._store["return_value"] = None
    request.node._store["fixture_values"] = fixture_values

    yield

    test_result = request.node._store.get("test_result", "UNKNOWN")
    test_return_value = request.node._store.get("return_value", "None")
    compat_compare = request.node._store.get("compat_compare", None)

    record = {
        "result": test_result,
        "return_value": test_return_value,
        "fixtures": fixture_values,
    }
    if compat_compare is not None:
        record["compat_compare"] = compat_compare

    test_results.append({test_name: record})

def pytest_sessionfinish(session, exitstatus):
    """
    Finalize session artifacts and optionally generate a performance report.

    - Copies `pytest.log` -> `debug.log` and `kernel_log.txt` -> `kernel.log`
      into `--resultpath` when provided.

    Args:
        session (pytest.Session): The pytest session (unused beyond state read).
        exitstatus (int): Pytest exit status code.
    """
    result_path = getattr(pytest, "_result_path", None)
    try:
        pytest._session_duration_seconds = max(0.0, time.time() - float(getattr(pytest, "_session_start_ts", time.time())))
    except Exception:
        pytest._session_duration_seconds = None
    destination_dir: Path | None = None
    csv_file = "test_results.csv"
    logging.info(test_results)

    compatibility_results = []
    for record in test_results:
        if not isinstance(record, dict) or not record:
            continue
        test_name = next(iter(record))
        data = record[test_name]
        fixtures = data.get("fixtures", {})
        if "router_setting" in fixtures or "power_setting" in fixtures:
            compatibility_results.append(record)

    if compatibility_results:
        write_compatibility_results(compatibility_results, csv_file)

    if result_path:
        destination_dir = Path(result_path)
        with suppress(Exception):
            destination_dir.mkdir(parents=True, exist_ok=True)

    # For compatibility cases, archive the CSV into the report directory and
    # sync both CSV + router catalogue into MySQL (best effort).
    csv_path_for_db = Path(csv_file).resolve()
    if compatibility_results and destination_dir:
        target_csv = destination_dir / csv_file
        shutil.copy(Path(csv_file), target_csv)
        csv_path_for_db = target_csv.resolve()

    if compatibility_results:
        from src.tools.mysql_tool.operations import sync_compatibility_artifacts_to_db
        from src.util.constants import load_config

        config = load_config(refresh=True) or {}
        router_json = str((Path.cwd() / "config" / "compatibility_router.json").resolve())
        case_path_hint = None
        try:
            args = getattr(session.config, "args", None) or []
            if args:
                case_path_hint = str(args[-1])
        except Exception:
            case_path_hint = None

        sync_compatibility_artifacts_to_db(
            config,
            csv_file=str(csv_path_for_db),
            router_json=router_json,
            case_path=case_path_hint,
            duration_seconds=getattr(pytest, "_session_duration_seconds", None),
        )

    src_log = Path("pytest.log")
    if destination_dir and src_log.exists():
        shutil.copy(src_log, destination_dir / "debug.log")

    ser_log = Path("kernel_log.txt")
    if destination_dir and ser_log.exists():
        try:
            shutil.copy(ser_log, destination_dir / "kernel.log")
        except Exception as exc:
            logging.warning("Failed to copy kernel_log.txt to %s: %s", destination_dir, exc)

    test_result = getattr(pytest, "testResult", None)
    if isinstance(test_result, PerformanceResult):
        _maybe_generate_project_report()

    # Generate an Allure HTML report under the per-run report directory when
    # available, using a history cache derived from the src/test subpath so
    # that each testcase family (peak/RVR/RVO/compatibility/etc.) maintains
    # its own historical trend.
    try:
        _generate_allure_report(session, destination_dir)
    except Exception:
        logging.debug("Allure report generation skipped/failed", exc_info=True)
