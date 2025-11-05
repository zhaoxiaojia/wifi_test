#!/usr/bin/env python 
# -*- coding: utf-8 -*-
"""
# File       : demo_.py
# Time       锛?023/6/29 13:36
# Author     锛歝hao.li
# version    锛歱ython 3.9
# Description锛?
"""

import os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from contextlib import suppress

import pytest
import csv
from src.tools.connect_tool.adb import adb
# from tools.connect_tool.host_os import host_os
from src.tools.connect_tool.telnet_tool import telnet_tool
from src.tools.TestResult import TestResult
from src.tools.config_loader import load_config
from src.dut_control.roku_ctrl import roku_ctrl
from src.tools.router_tool.Router import Router
from src.tools.reporting import generate_project_report
from src.test.pyqt_log import emit_pyqt_message

try:
    import sitecustomize  # type: ignore
except Exception:  # pragma: no cover - defensive, sitecustomize is optional at runtime
    sitecustomize = None

# pytest_plugins = "util.report_plugin"
test_results = []
import logging

logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
    format="%(asctime)s | %(levelname)s | %(filename)s:%(funcName)s(line:%(lineno)d) |  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True
)



_FILENAME_SANITIZE_PATTERN = re.compile(r"[^0-9A-Za-z._-]+")


def _sanitize_filename_component(value) -> str:
    text = ""
    if value is not None:
        text = str(value).strip()
    if not text:
        return ""
    sanitized = _FILENAME_SANITIZE_PATTERN.sub("_", text)
    return sanitized.strip("_")


def _maybe_generate_project_report() -> None:
    config = getattr(pytest, "config", {}) or {}
    fpga_cfg = config.get("fpga") or {}
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
            logging.info("Using selected Wi-Fi test type for project report: %s", forced_type)
        else:
            logging.warning(
                "Multiple Wi-Fi test types detected (%s); fallback to auto detection.",
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
        logging.info("Generated project Wi-Fi performance report: %s", output_path)
    except Exception:
        logging.exception("Failed to generate project Wi-Fi performance report")


def pytest_sessionstart(session):
    '''
    Frame Run Pre-Action Runs only once per frame start
    :param session:
    :return:
    '''
    # get host os
    # pytest.host_os = host_os()
    # get the pc system
    if ('win32' or 'win64') in sys.platform:
        pytest.win_flag = True
    else:
        pytest.win_flag = False
    # The configuration information of  DUT
    pytest.config = load_config(refresh=True) or {}
    # The connection method to the product to DUT
    pytest.chip_info = pytest.config.get('fpga')
    connect_cfg = pytest.config.get('connect_type') or {}
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
    rvr_cfg = pytest.config.get('rvr') or {}
    try:
        repeat_times = int(rvr_cfg.get('repeat', 0) or 0)
    except Exception:
        repeat_times = 0
    if pytest.connect_type == 'Android':
        # Create adb obj
        adb_cfg = connect_cfg.get('Android') or connect_cfg.get('adb') or {}
        device = adb_cfg.get('device')
        if device is None:
            # Obtain the device number dynamically
            info = subprocess.check_output("adb devices", shell=True, encoding='utf-8')
            device = re.findall(r'\n(.*?)\s+device', info, re.S)
            if device: device = device[0]
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
    pytest._result_path = session.config.getoption("--resultpath") or os.getcwd()
    pytest._testresult_repeat_times = repeat_times
    pytest.testResult = None
    if os.path.exists('temp.txt'):
        os.remove('temp.txt')


def pytest_addoption(parser):
    parser.addoption("--resultpath", action="store", default=None, help="Test result path")


def pytest_collection_finish(session):
    # 鏀堕泦瀹屾瘯锛岃褰曟€荤敤渚嬫暟
    session.total_test_count = len(session.items)
    # logging.info(f"[PYQT_TOTAL]{session.total_test_count}")
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
        logging.info("Detected selected Wi-Fi test types: %s", ", ".join(sorted(selected_types)))
    else:
        pytest.selected_test_types = set()

    result_path = getattr(pytest, "_result_path", None)
    repeat_times = getattr(pytest, "_testresult_repeat_times", 0)
    needs_performance_logging = any(kind in {"RVR", "RVO", "PERFORMANCE"} for kind in selected_types)
    if needs_performance_logging:
        logdir = result_path or os.getcwd()
        pytest.testResult = TestResult(logdir, [], repeat_times)
    else:
        pytest.testResult = None
        if "STABILITY" in selected_types:
            logging.info("Performance log artifacts disabled for stability-only execution")


def pytest_runtest_setup(item):
    emit_pyqt_message("CASE", item.originalname)


def pytest_runtest_logreport(report):
    if report.when == "setup" and hasattr(report, "nodeid"):
        test_nodeid = report.nodeid
        if "[" in test_nodeid:
            params = test_nodeid.split("[", 1)[-1].rstrip("]")
            logging.info("Test params: %s", params)


# @pytest.fixture(autouse=True)
# def record_test_data(request):
#     """
#     鑷姩鏀堕泦娴嬭瘯鐢ㄤ緥鐨?fixture 鍙傛暟 ids锛屽苟瀛樺偍杩斿洖鍊?
#     """
#     test_name = request.node.originalname  # 鑾峰彇娴嬭瘯鍚嶇О
#     logging.info(f'test_name {test_name}')
#     fixture_values = {}
#     # 閬嶅巻鎵€鏈?fixture 骞跺瓨鍌ㄨ繑鍥炲€?
#     for fixture_name in request.node.fixturenames:
#         if fixture_name in request.node.funcargs:
#             fixture_values[fixture_name] = request.node.funcargs[fixture_name]
#
#     # 纭繚 request.node._store 瀛樺湪
#     request.node._store = getattr(request.node, "_store", {})
#     request.node._store["return_value"] = None  # 鍒濆鍖栬繑鍥炲€?
#     request.node._store["fixture_values"] = fixture_values  # 璁板綍 fixture 杩斿洖鍊?
#
#     yield  # 璁╂祴璇曟墽琛?
#     # 鑾峰彇娴嬭瘯缁撴灉
#     test_result = request.node._store.get("test_result", "UNKNOWN")  # 杩欓噷鏀逛负浠?_store 鑾峰彇
#     # 鑾峰彇娴嬭瘯鏂规硶鐨勮繑鍥炲€?
#     test_return_value = request.node._store.get("return_value", "None")
#     # 瀛樺偍鍒板叏灞€瀛楀吀
#     test_results.append({test_name: {
#         "result": test_result,
#         "return_value": test_return_value,
#         "fixtures": fixture_values
#     }})


def pytest_collection_modifyitems(config, items):
    # item琛ㄧず鏀堕泦鍒扮殑娴嬭瘯鐢ㄤ緥锛屽浠栬繘琛岄噸鏂扮紪鐮佸鐞?
    new_items = []
    for item in items:
        item.name = item.name.encode("utf-8").decode("unicode-escape")
        item._nodeid = item._nodeid.encode("utf-8").decode("unicode-escape")
        func = item.function


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    if report.when == 'setup':
        if report.failed:
            item._store['test_result'] = "FAIL"
    elif report.when == 'call':
        item._store['test_result'] = "PASS" if report.passed else "FAIL" if report.failed else "SKIPP"
        if not report.failed:
            return_value = getattr(call, "result", None) or item._store.get("return_value", None)
            logging.info(f'record return value: {call.result}')
            item._store["return_value"] = return_value


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
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


def pytest_sessionfinish(session, exitstatus):
    csv_file = "../test_results.csv"
    # global test_results  # 纭繚test_results鍦ㄥ嚱鏁颁腑鍙敤
    #
    # # 瀹氫箟琛ㄥご
    # title_data = ['PDU IP', 'PDU Port', 'AP Brand', 'Band', 'Ssid', 'WiFi Mode', 'Bandwidth', 'Security',
    #               'Scan', 'Connect', 'TX Result', 'Channel', 'RSSI', 'TX Criteria', 'TX  Throughtput(Mbps)',
    #               'RX  Result', 'Channel', 'RSSI',
    #               'RX Criteria', 'RX Throughtput(Mbps)']
    #
    # # 鍐欏叆琛ㄥご
    # with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
    #     writer = csv.writer(file, quotechar=' ')
    #     writer.writerow(title_data)
    #
    # logging.info(test_results)
    #
    # row_data = []
    # temp_data = []
    #
    # # 澶勭悊姣忎釜娴嬭瘯缁撴灉
    # for test_result in test_results:
    #     try:
    #         # 鑾峰彇娴嬭瘯鍚嶇О
    #         test_name = sorted(test_result.keys())[0]
    #
    #         # 妫€鏌ユ槸鍚﹂渶瑕佸啓鍏ュ墠涓€琛屾暟鎹?
    #         if test_name in temp_data:
    #             if row_data:  # 纭繚鏈夋暟鎹彲鍐?
    #                 with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
    #                     writer = csv.writer(file, quotechar=' ')
    #                     writer.writerow(row_data)
    #             row_data.clear()
    #             temp_data.clear()
    #
    #         # 鑾峰彇娴嬭瘯鏁版嵁
    #         data = test_result[test_name]
    #
    #         # 澶勭悊fixtures鏁版嵁
    #         if 'fixtures' in data and data['fixtures']:
    #             keys = sorted(data['fixtures'].keys())
    #             if data['fixtures'][keys[0]][0] not in row_data:
    #                 for j in keys:
    #                     try:
    #                         logging.info(f"fixture {type(data['fixtures'][j])}")
    #                         if isinstance(data['fixtures'][j], dict):
    #                             if data['fixtures'][j].get('ip') and data['fixtures'][j]['ip'] not in row_data:
    #                                 row_data.append(data['fixtures'][j]['ip'])
    #                             if data['fixtures'][j].get('port') and data['fixtures'][j]['port'] not in row_data:
    #                                 row_data.append(data['fixtures'][j]['port'])
    #                             if data['fixtures'][j].get('brand') and \
    #                                     f"{data['fixtures'][j]['brand']} {data['fixtures'][j]['model']}" not in row_data:
    #                                 row_data.append(f"{data['fixtures'][j]['brand']} {data['fixtures'][j]['model']}")
    #                         elif isinstance(data['fixtures'][j], Router):
    #                             router_str = str(data['fixtures'][j]).replace('default,', '')
    #                             if router_str not in row_data:
    #                                 row_data.append(router_str)
    #                     except KeyError as e:
    #                         logging.warning(f"KeyError in fixture processing: {e}")
    #                         continue  # 缁х画澶勭悊涓嬩竴涓猣ixture
    #
    #         temp_data.append(test_name)
    #
    #         # 娣诲姞娴嬭瘯缁撴灉鍜岃繑鍥炲€?
    #         if 'result' in data and data['result']:
    #             row_data.append(data['result'])
    #         if 'return_value' in data and data['return_value']:
    #             row_data.extend([*data['return_value']])
    #
    #     except (KeyError, IndexError) as e:
    #         logging.error(f"Error processing test result: {e}")
    #         continue  # 缁х画澶勭悊涓嬩竴涓祴璇曠粨鏋?
    #
    # # 鍐欏叆鏈€鍚庝竴琛屾暟鎹?
    # if row_data:
    #     with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
    #         writer = csv.writer(file, quotechar=' ')
    #         writer.writerow(row_data)

    result_path = getattr(pytest, "_result_path", None)
    destination_dir: Path | None = None
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

    test_result = getattr(pytest, "testResult", None)
    if sitecustomize and hasattr(sitecustomize, "flush_python_run_log"):
        try:
            sitecustomize.flush_python_run_log()
        except Exception as exc:
            logging.warning("Failed to flush python_run.log: %s", exc)
    python_run_env = os.environ.get("PYTHON_RUN_ROOT_LOG")
    python_run_src = Path(python_run_env) if python_run_env else None
    if isinstance(test_result, TestResult):
        try:
            logdir = Path(getattr(test_result, "logdir", "") or "").resolve()
        except Exception:
            logdir = None
        else:
            if logdir:
                with suppress(Exception):
                    logdir.mkdir(parents=True, exist_ok=True)
                if python_run_src and python_run_src.is_file():
                    try:
                        shutil.copy2(python_run_src, logdir / python_run_src.name)
                        logging.info("Archived python_run.log to %s", logdir)
                    except Exception as exc:
                        logging.warning(
                            "Failed to archive python_run.log to %s: %s", logdir, exc
                        )
    if isinstance(test_result, TestResult):
        _maybe_generate_project_report()
    # shutil.copy("report.html", "report_bat.html")
    # shutil.move("report_bat.html", pytest.testResult.logdir)
