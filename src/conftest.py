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
import subprocess
import logging
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Annotated

import pytest
import csv  # noqa: F401  (kept for potential future CSV export)

from src.tools.connect_tool.adb import adb
from src.tools.connect_tool.serial_tool import serial_tool
from src.tools.connect_tool.telnet_tool import telnet_tool
from src.tools.connect_tool.local_os import LocalOS
from src.tools.performance_result import PerformanceResult
from src.tools.config_loader import load_config
from src.dut_control.roku_ctrl import roku_ctrl
from src.tools.router_tool.Router import Router
from src.tools.reporting import generate_project_report
from src.test.pyqt_log import emit_pyqt_message
from src.test.compatibility.results import write_compatibility_results

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
    format="%(asctime)s | %(levelname)s | %(filename)s:%(funcName)s(line:%(lineno)d) |  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
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
    # get host os
    if ('win32' or 'win64') in sys.platform:
        pytest.win_flag = True
    else:
        pytest.win_flag = False
    pytest.host_os = LocalOS()
    # Load configuration (fresh)
    pytest.config = load_config(refresh=True) or {}

    # Connection type setup
    connect_cfg = pytest.config.get("connect_type") or {}
    connect_type_value = connect_cfg.get('type', 'Android')
    if isinstance(connect_type_value, str):
        connect_type_value = connect_type_value.strip() or 'Android'
        lowered = connect_type_value.lower()
        if lowered == 'adb':
            connect_type_value = 'Android'
        elif lowered == 'telnet':
            connect_type_value = 'Linux'
    else:
        connect_type_value = 'Android'
    pytest.connect_type = connect_type_value
    pytest.third_party_cfg = connect_cfg.get('third_party', {})

    # Serial (kernel log) setup
    rvr_cfg = pytest.config.get('rvr') or {}
    serial_cfg = pytest.config.get('serial_port') or {}
    pytest.serial = None
    status = serial_cfg.get('status')
    serial_enabled = status if isinstance(status, bool) else str(status).strip().lower() in {'1', 'true', 'yes', 'on'}
    if serial_enabled:
        try:
            pytest.serial = serial_tool(
                serial_port=serial_cfg.get('port', ''),
                baud=serial_cfg.get('baud', '')
            )
            logging.info("Serial logging enabled; kernel_log.txt will be captured.")
        except Exception:
            logging.exception("Failed to initialize serial tool; serial logging disabled.")

    # Repeat times
    try:
        repeat_times = int(rvr_cfg.get('repeat', 0) or 0)
    except Exception:
        repeat_times = 0

    # DUT connection
    if pytest.connect_type == 'Android':
        # Create adb obj
        adb_cfg = connect_cfg.get('Android') or connect_cfg.get('adb') or {}
        device = adb_cfg.get('device')
        if device is None:
            # Obtain the device number dynamically
            info = subprocess.check_output("adb devices", shell=True, encoding='utf-8')
            device = re.findall(r'\n(.*?)\s+device', info, re.S)
        pytest.dut = adb(serialnumber=device if device else '')
    elif pytest.connect_type == 'Linux':
        # Create telnet obj
        telnet_cfg = connect_cfg.get('Linux') or connect_cfg.get('telnet') or {}
        telnet_ip = telnet_cfg.get('ip')
        if not telnet_ip:
            raise EnvironmentError("Not support connect type Linux: missing IP address")
        pytest.dut = telnet_tool(telnet_ip)
        pytest.dut.roku = roku_ctrl(telnet_ip)
    else:
        raise EnvironmentError("Not support connect type %s" % pytest.connect_type)

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


def pytest_collection_finish(session):
    """
    After test collection completes:
      - Detect selected Wi‑Fi test types from collected paths.
      - Record total test count for PyQt progress display.

    Args:
        session (pytest.Session): The current pytest session object.
    """
    # Number of tests collected
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
    if not hasattr(session, 'pyqt_finished'):
        session.pyqt_finished = 0
    if getattr(item, '_pyqt_progress_recorded', False):
        return
    session.pyqt_finished += 1
    total = getattr(session, 'total_test_count', None)
    if total:
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
    test_results.append({test_name: {
        "result": test_result,
        "return_value": test_return_value,
        "fixtures": fixture_values
    }})

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
    destination_dir: Path | None = None
    csv_file = "test_results.csv"
    logging.info(test_results)
    write_compatibility_results(test_results, csv_file)
    if result_path:
        destination_dir = Path(result_path)
        with suppress(Exception):
            destination_dir.mkdir(parents=True, exist_ok=True)

    src_log = Path("pytest.log")
    if destination_dir and src_log.exists():
        try:
            shutil.copy(src_log, destination_dir / "debug.log")
        except Exception as exc:
            logging.warning("Failed to copy pytest.log to %s: %s", destination_dir, exc)

    ser_log = Path("kernel_log.txt")
    if destination_dir and ser_log.exists():
        try:
            shutil.copy(ser_log, destination_dir / "kernel.log")
        except Exception as exc:
            logging.warning("Failed to copy pytest.log to %s: %s", destination_dir, exc)

    test_result = getattr(pytest, "testResult", None)
    if isinstance(test_result, PerformanceResult):
        _maybe_generate_project_report()

    # (Deliberately not moving report.html artifacts here; handled elsewhere.)