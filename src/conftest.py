#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Pytest session configuration and hooks for the Wi‑Fi test framework.

This module configures logging, prepares DUT connections (ADB/Telnet),
collects run-time metadata for PyQt UI, and optionally generates
a Wi‑Fi performance report at session end for specific customers.
"""

from __future__ import annotations

import os, json
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
import pandas as pd
from openpyxl.styles import Font

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
from collections import defaultdict

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

# Step_Result：{ test_case_id -> [ (step_desc, status, details), ... ] }
if not hasattr(pytest, "test_step_results"):
    pytest.test_step_results = defaultdict(list)

# ------------------------------------# Helpers# -----------------------------
def get_resource_path(relative_path: str) -> Path:
    """获取资源绝对路径（兼容开发环境和 PyInstaller 打包）"""
    import sys
    if getattr(sys, 'frozen', False):
        # 打包后的 EXE：资源在 _MEIPASS 下
        base_path = Path(sys._MEIPASS)
    else:
        # 开发环境：资源在项目根目录（conftest.py 的上两级）
        base_path = Path(__file__).parent.parent
    return base_path / relative_path

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
    Generates a static Allure HTML report.
    - Input: The directory containing Allure .json result files.
    - Output: A static HTML report in the 'allure-report' subdirectory of destination_dir.
    """
    if destination_dir is None:
        logging.warning("No destination_dir provided for Allure report generation.")
        return

    # --- 关键修改 1: 正确推断输入目录 ---
    # 假设您的 .json 文件就直接放在 destination_dir 下 (即 report/2026.01.08_.../)
    input_dir = destination_dir / "allure_report"
    # --- 关键修复：增加重试机制 ---
    max_retries = 5
    retry_delay = 1  # 秒

    for attempt in range(max_retries):
        if not input_dir.exists():
            logging.debug(f"[Attempt {attempt + 1}] Allure dir not found: {input_dir}")
            time.sleep(retry_delay)
            continue

        json_files = list(input_dir.glob("*.json"))
        logging.debug(f"[Attempt {attempt + 1}] Found {len(json_files)} .json files: {[f.name for f in json_files]}")
        print(f"[DEBUG] Found json files in : {json_files}")
        if json_files:
            logging.info("Allure result files found. Proceeding to generate report.")
            break  # 找到文件，跳出循环

        logging.debug(f"No .json files found on attempt {attempt + 1}. Retrying...")
        time.sleep(retry_delay)
    else:
        # 所有重试都失败了
        logging.warning(
            "Allure input directory is empty after %d retries: %s. "
            "Directory contents: %s",
            max_retries,
            input_dir,
            [f.name for f in input_dir.iterdir()] if input_dir.exists() else "DIR NOT FOUND"
        )
        return

    # --- 关键修改 2: 设置正确的输出目录 ---
    output_dir = destination_dir / "allure-report"
    output_dir.mkdir(parents=True, exist_ok=True)
    # --- 修改 2 结束 ---

    allure_exe = _find_allure_executable()
    if allure_exe is None:
        logging.error("Allure CLI not found. Please ensure 'allure' is in your PATH.")
        return

    try:
        # 构建并执行命令
        cmd = [
            allure_exe,
            "generate",
            str(input_dir.resolve()),  # 输入目录
            "-o", str(output_dir.resolve()), # 输出目录
            "--clean" # 清理旧报告
        ]
        logging.info("Executing command: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logging.info("Allure report generated successfully at: %s", output_dir)

        # 报告生成成功后，删除原始的 JSON 数据目录
        # if input_dir.exists():
        #     shutil.rmtree(input_dir)
        #     logging.info("Cleaned up original Allure results directory: %s", input_dir)
    except subprocess.CalledProcessError as e:
        logging.error("Failed to generate Allure report. Command: %s\nStdout: %s\nStderr: %s",
                      " ".join(cmd), e.stdout, e.stderr)
    except Exception as e:
        logging.error("Unexpected error during Allure report generation: %s", e)


def _generate_allure_report_cli(input_dir: Path, output_dir: Path) -> None:
    """
    Generates a static Allure HTML report from a given input directory.

    This is a more flexible version of the original _generate_allure_report,
    designed to work with both single-case and ExcelPlanRunner modes.

    Args:
        input_dir (Path): Directory containing Allure .json result files.
        output_dir (Path): Directory where the static HTML report will be generated.
    """

    if not input_dir.exists():
        logging.warning("Allure input directory does not exist: %s", input_dir)
        return

    json_files = list(input_dir.glob("*.json"))
    if not json_files:
        logging.warning("No .json files found in Allure input directory: %s", input_dir)
        return

    logging.info("Found %d Allure result files. Generating report...", len(json_files))
    output_dir.mkdir(parents=True, exist_ok=True)

    allure_exe = _find_allure_executable()
    if allure_exe is None:
        logging.error("Allure CLI not found. Please ensure 'allure' is in your PATH.")
        return

    try:
        cmd = [
            allure_exe,
            "generate",
            str(input_dir.resolve()),
            "-o",
            str(output_dir.resolve()),
            "--clean"
        ]
        logging.info("Executing command: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logging.info("Allure report generated successfully at: %s", output_dir)

        # 注意：不再自动删除 input_dir，因为 ExcelPlanRunner 需要它持续存在
        # if input_dir.exists():
        #     shutil.rmtree(input_dir)
        #     logging.info("Cleaned up original Allure results directory: %s", input_dir)

    except subprocess.CalledProcessError as e:
        logging.error("Failed to generate Allure report. Command: %s\nStdout: %s\nStderr: %s", " ".join(cmd),
                      e.stdout, e.stderr)
    except Exception as e:
        logging.error("Unexpected error during Allure report generation: %s", e)

def _generate_allure_report_offline(input_dir: Path, output_dir: Path) -> None:
    """
    【智能模式】自动选择 Allure 生成方式：
    1. 优先使用 EXE 内嵌的 Allure + JRE（PyInstaller 模式）
    2. 若内嵌缺失，则回退到系统 PATH 中的 'allure' 命令
    """
    logger = logging.getLogger(__name__)
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()

    if not input_dir.exists():
        logger.error("❌ Allure input directory does NOT exist: %s", input_dir)
        return

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        logger.warning("⚠️ No .json files found in Allure input directory: %s", input_dir)
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # --- 尝试 1: 使用内嵌 Allure (PyInstaller 模式) ---
    meipass = getattr(sys, '_MEIPASS', '')
    if meipass:
        allure_exe = Path(meipass) / "allure" / "bin" / "allure.bat"
        jre_home = Path(meipass) / "jre"

        if allure_exe.exists() and (jre_home / "bin" / "java.exe").exists():
            logger.info("🔧 Using embedded Allure from PyInstaller bundle...")
            cmd = [str(allure_exe), "generate", str(input_dir), "-o", str(output_dir), "--clean"]
            env = os.environ.copy()
            env["JAVA_HOME"] = str(jre_home)
            env["PATH"] = str(jre_home / "bin") + os.pathsep + env["PATH"]
            try:
                result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    logger.info("✅ Embedded Allure report generated successfully at: %s", output_dir)
                    return  # 成功，直接返回
                else:
                    logger.warning("⚠️ Embedded Allure failed, falling back to system 'allure'...")
            except Exception as e:
                logger.warning("⚠️ Embedded Allure execution error, falling back: %s", e)

    # --- 尝试 2: 回退到系统 PATH 中的 'allure' ---
    logger.info("🔄 Falling back to system-installed 'allure' command...")
    allure_cmd = shutil.which("allure")
    if not allure_cmd:
        logger.error("❌ Allure CLI not found in system PATH and no embedded version available.")
        return

    cmd = [allure_cmd, "generate", str(input_dir), "-o", str(output_dir), "--clean"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            logger.info("✅ System Allure report generated successfully at: %s", output_dir)
        else:
            logger.error("❌ System Allure failed. Stderr: %s", result.stderr)
    except subprocess.TimeoutExpired:
        logger.error("⏰ Allure command timed out after 60 seconds.")
    except Exception as e:
        logger.exception("💥 Unexpected error during system Allure report generation: %s", e)


# ----------------------------------------------------------------------------#
# Public API for external report generation (e.g., ExcelPlanRunner)
# ----------------------------------------------------------------------------#
def generate_allure_html_report(input_dir: Path, output_dir: Path) -> None:
    """
    Public wrapper for _generate_allure_report_v2.
    Generates Allure HTML report from input_dir (.json files) to output_dir.
    """
    _generate_allure_report_cli(input_dir, output_dir)

# ----------------------------------------------------------------------------#
# Public API for external report generation (e.g., ExcelPlanRunner)
# ----------------------------------------------------------------------------#
def generate_allure_html_report(input_dir: Path, output_dir: Path) -> None:
    """
    Public wrapper for _generate_allure_report_v2.
    Generates Allure HTML report from input_dir (.json files) to output_dir.
    """
    _generate_allure_report_cli(input_dir, output_dir)

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
        item._store['test_result'] = "PASS" if report.passed else "FAIL" if report.failed else "SKIP"
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


def pytest_sessionfinish(session, exitstatus):
    """ Finalize session artifacts and optionally generate a performance report.
    - Copies `pytest.log` -> `debug.log` and `kernel_log.txt` -> `kernel.log` into `--resultpath` when provided.
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

    # --- [原有逻辑] 处理兼容性结果 ---
    logging.info(f"🔍 Total test_results count: {len(test_results)}")
    logging.info(f"🔍 Raw test_results: {test_results}")

    compatibility_results = []
    for record in test_results:
        if not isinstance(record, dict) or not record:
            continue
        test_name = next(iter(record))
        data = record[test_name]
        fixtures = data.get("fixtures", {})
        if "event_loop_policy" in fixtures:
            del fixtures["event_loop_policy"]

        if "router_setting" in fixtures or "power_setting" in fixtures:
            compatibility_results.append(record)

    logging.info(f"✅ Final compatibility_results count: {len(compatibility_results)}")

    if compatibility_results:
        write_compatibility_results(compatibility_results, csv_file)
        logging.info(f"✅ Wrote test_results.csv with {len(compatibility_results)} records")
    else:
        logging.warning("⚠️ No compatibility results found! Skipping test_results.csv")

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

        # --- [原有逻辑] 复制日志文件 ---
        src_log = Path("pytest.log")
        if destination_dir and src_log.exists():
            shutil.copy(src_log, destination_dir / "debug.log")

        ser_log = Path("kernel_log.txt")
        if destination_dir and ser_log.exists():
            try:
                shutil.copy(ser_log, destination_dir / "kernel.log")
            except Exception as exc:
                logging.warning("Failed to copy kernel_log.txt to %s: %s", destination_dir, exc)
    # --- [原有逻辑结束] ---

    # --- 【新增】处理项目性能报告 (XIAOMI) ---
    test_result = getattr(pytest, "testResult", None)
    if isinstance(test_result, PerformanceResult):
        _maybe_generate_project_report()
    # --- 【新增结束】---

    # --- 【关键修改】智能生成 Allure 报告 ---
    # 默认行为：destination_dir 是单 Case 的报告目录，input_dir 是其下的 allure_report
    input_dir_for_allure = None
    output_dir_for_allure = None

    if destination_dir is not None:
        # 检查是否存在共享的 allure_results 目录 (ExcelPlanRunner 模式)
        shared_allure_results = destination_dir / "allure_report"
        if shared_allure_results.exists() and any(shared_allure_results.iterdir()):
            # ========== ExcelPlanRunner 共享模式 ==========
            # 输入：共享的 allure_results 目录
            input_dir_for_allure = shared_allure_results
            # 输出：在同一个主报告目录下生成 allure-report
            output_dir_for_allure = destination_dir / "allure_results"
            logging.info("Detected ExcelPlanRunner mode. Generating report from shared 'allure_results'.")
        else:
            # ========== 单 Case 独立模式 (保持原样) ==========
            # 输入：原有的 allure_report 目录
            input_dir_for_allure = destination_dir / "allure_report"
            # 输出：在同一个 Case 报告目录下生成 allure-report
            output_dir_for_allure = destination_dir / "allure_results"

    # 调用通用的报告生成函数
    if input_dir_for_allure is not None and output_dir_for_allure is not None:
        # 智能选择生成方式：本地用 CLI，打包用离线
        import sys
        if getattr(sys, 'frozen', False):
            _generate_allure_report_offline(input_dir_for_allure, output_dir_for_allure)
        else:
            _generate_allure_report_cli(input_dir_for_allure, output_dir_for_allure)
    else:
        logging.warning("Could not determine Allure input/output directories.")
    # --- 【关键修改结束】---

    # --- 【新增】通用测试步骤报告写入 ---
    if hasattr(pytest, "test_step_results") and pytest.test_step_results:
        for tcid, steps in pytest.test_step_results.items():
            # 聚合所有步骤为多行文本
            step_messages = []
            all_passed = True

            for desc, status, details in steps:
                emoji = "✅" if status == "PASS" else ("❌" if status == "FAIL" else "⚠️")
                msg = f"{emoji} {desc}"
                if details:
                    msg += f": {details}"
                step_messages.append(msg)

                if status != "PASS":
                    all_passed = False

            final_status = "Passed" if all_passed else "Failed"
            step_details = "\n".join(step_messages)

            # 调用现有 Excel 写入函数（需确保它支持通用 TCID）
            _update_excel_with_tcid_result(tcid, final_status, step_details)

def record_test_step(tcid: str, step_desc: str, status: str, details: str = ""):
    """
    供测试脚本调用，记录单个测试步骤结果。

    Args:
        tcid: 测试用例 ID，如 "TC_WIFI_INIT_001"
        step_desc: 步骤描述，如 "Wi-Fi enabled"
        status: "PASS" / "FAIL" / "SKIP"
        details: 附加信息（可选）
    """
    pytest.test_step_results[tcid].append((step_desc, status, details))
    logging.info(f"Test step {tcid + ' ' + step_desc}: {step_desc}")


def _update_excel_with_tcid_result(tcid: str, final_status: str, step_details: str):
    """
    根据 TCID 更新 test_result.xlsx 中的状态和步骤详情。

    Args:
        tcid (str): 测试用例 ID，如 "WiFi-STA-FDF0001"
        final_status (str): 最终状态，如 "Passed" / "Failed"
        step_details (str): 多行字符串，包含每个步骤的 emoji + 描述
    """
    # 获取报告目录（从环境变量）
    report_dir = os.getenv("PYTEST_REPORT_DIR")
    if not report_dir:
        logging.warning("PYTEST_REPORT_DIR not set, skipping Excel update.")
        return

    excel_path = Path(report_dir) / "test_result.xlsx"
    if not excel_path.exists():
        logging.error(f"Excel file not found: {excel_path}")
        return

    try:
        # 读取 Excel（确保 TCID 列为字符串）
        df = pd.read_excel(excel_path, dtype={"TCID": str})

        # 查找匹配的 TCID 行（忽略前后空格）
        mask = df["TCID"].astype(str).str.strip() == tcid.strip()
        if not mask.any():
            logging.warning(f"TCID '{tcid}' not found in Excel.")
            return

        # 更新第一匹配行（通常唯一）
        idx = mask.idxmax()
        df.loc[idx, "Status"] = final_status
        df.loc[idx, "Step_Details"] = str(step_details)[:32767]

        # 写回文件（使用 openpyxl 引擎保持格式）
        df.to_excel(excel_path, index=False, engine='openpyxl')
        logging.info(f"✅ Updated Excel for TCID={tcid}: {final_status}")

    except Exception as e:
        logging.error(f"❌ Failed to update Excel for TCID={tcid}: {e}")
