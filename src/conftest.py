#!/usr/bin/env python 
# -*- coding: utf-8 -*-
"""
# File       : conftest.py
# Time       ：2023/6/29 13:36
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import re
import shutil
import subprocess

import pytest
import csv
from src.tools.connect_tool.adb import adb
# from tools.connect_tool.host_os import host_os
from src.tools.connect_tool.telnet_tool import telnet_tool
from src.tools.TestResult import TestResult
from src.tools.yamlTool import yamlTool
from src.dut_control.roku_ctrl import roku_ctrl
from src.tools.router_tool.Router import Router

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
    if pytest.win_flag:
        pytest.config_yaml = yamlTool(os.getcwd() + '\\config\\config.yaml')
    else:
        pytest.config_yaml = yamlTool(os.getcwd() + '/config/config.yaml')
    # The connection method to the product to DUT
    pytest.chip_info = pytest.config_yaml.get_note('fpga')
    pytest.connect_type = pytest.config_yaml.get_note('connect_type')['type']
    if pytest.connect_type == 'adb':
        # Create adb obj
        device = pytest.config_yaml.get_note("connect_type")[pytest.connect_type]['device']
        if device is None:
            # Obtain the device number dynamically
            info = subprocess.check_output("adb devices", shell=True, encoding='utf-8')
            device = re.findall(r'\n(.*?)\s+device', info, re.S)
            if device: device = device[0]
        pytest.dut = adb(serialnumber=device if device else '')
    elif pytest.connect_type == 'telnet':
        # Create telnet obj
        telnet_ip = pytest.config_yaml.get_note("connect_type")[pytest.connect_type]['ip']
        pytest.dut = telnet_tool(telnet_ip)
        pytest.dut.roku = roku_ctrl(telnet_ip)
    else:
        raise EnvironmentError("Not support connect type %s" % pytest.connect_type)
    pytest.testResult = TestResult(session.config.getoption("--resultpath"), [])
    if os.path.exists('temp.txt'):
        os.remove('temp.txt')


def pytest_addoption(parser):
    parser.addoption("--resultpath", action="store", default=None, help="Test result path")


def pytest_collection_finish(session):
    # 收集完毕，记录总用例数
    session.total_test_count = len(session.items)
    logging.info(f"[PYQT_TOTAL]{session.total_test_count}")


def pytest_runtest_logreport(report):
    if report.when == "setup" and hasattr(report, "nodeid"):
        test_nodeid = report.nodeid
        if "[" in test_nodeid:
            params = test_nodeid.split("[", 1)[-1].rstrip("]")
            logging.info('*' * 80)
            logging.info(f"* Test params: {params}")
            logging.info('*' * 80)


@pytest.fixture(autouse=True)
def record_test_data(request):
    """
    自动收集测试用例的 fixture 参数 ids，并存储返回值
    """
    test_name = request.node.originalname  # 获取测试名称
    logging.info(test_name)
    fixture_values = {}  # 存储 fixture 返回值
    # 遍历所有 fixture 并存储返回值
    for fixture_name in request.node.fixturenames:
        if fixture_name in request.node.funcargs:
            fixture_values[fixture_name] = request.node.funcargs[fixture_name]
    # 确保 request.node._store 存在
    request.node._store = getattr(request.node, "_store", {})
    request.node._store["return_value"] = None  # 初始化返回值
    request.node._store["fixture_values"] = fixture_values  # 记录 fixture 返回值

    yield  # 让测试执行
    # 获取测试结果
    test_result = request.node._store.get("test_result", "UNKNOWN")  # 这里改为从 _store 获取
    # 获取测试方法的返回值
    test_return_value = request.node._store.get("return_value", "None")
    # 存储到全局字典
    test_results.append({test_name: {
        "result": test_result,
        "return_value": test_return_value,
        "fixtures": fixture_values
    }})


def pytest_collection_modifyitems(config, items):
    # item表示收集到的测试用例，对他进行重新编码处理
    new_items = []
    for item in items:
        item.name = item.name.encode("utf-8").decode("unicode-escape")
        item._nodeid = item._nodeid.encode("utf-8").decode("unicode-escape")
        func = item.function


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    # 只在第一次统计这个 item
    if not hasattr(item, '_counted_progress'):
        session = item.session
        if not hasattr(session, 'pyqt_finished'):
            session.pyqt_finished = 0
        session.pyqt_finished += 1
        item._counted_progress = True  # 避免重复统计
        total = getattr(session, 'total_test_count', None)
        if total:
            print(f"[PYQT_PROGRESS] {session.pyqt_finished}/{total}", flush=True)

    # 原有返回值逻辑保留
    if report.when == 'call':
        item._store['test_result'] = "PASS" if report.passed else "FAIL" if report.failed else "SKIPP"
        if not report.failed:
            return_value = getattr(call, "result", None) or item._store.get("return_value", None)
            logging.info(f'record return value: {call.result}')
            item._store["return_value"] = return_value


def pytest_sessionfinish(session, exitstatus):
    csv_file = "../test_results.csv"
    global test_results  # 确保test_results在函数中可用

    # 定义表头
    title_data = ['PDU IP', 'PDU Port', 'AP Brand', 'Band', 'Ssid', 'WiFi Mode', 'Bandwidth', 'Security',
                  'Scan', 'Connect', 'TX Result', 'Channel', 'RSSI', 'TX Criteria', 'TX  Throughtput(Mbps)',
                  'RX  Result', 'Channel', 'RSSI',
                  'RX Criteria', 'RX Throughtput(Mbps)']

    # 写入表头
    with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, quotechar=' ')
        writer.writerow(title_data)

    logging.info(test_results)

    row_data = []
    temp_data = []

    # 处理每个测试结果
    for test_result in test_results:
        try:
            # 获取测试名称
            test_name = sorted(test_result.keys())[0]

            # 检查是否需要写入前一行数据
            if test_name in temp_data:
                if row_data:  # 确保有数据可写
                    with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
                        writer = csv.writer(file, quotechar=' ')
                        writer.writerow(row_data)
                row_data.clear()
                temp_data.clear()

            # 获取测试数据
            data = test_result[test_name]

            # 处理fixtures数据
            if 'fixtures' in data and data['fixtures']:
                keys = sorted(data['fixtures'].keys())
                if data['fixtures'][keys[0]][0] not in row_data:
                    for j in keys:
                        try:
                            logging.info(f"fixture {type(data['fixtures'][j])}")
                            if isinstance(data['fixtures'][j], dict):
                                if data['fixtures'][j].get('ip') and data['fixtures'][j]['ip'] not in row_data:
                                    row_data.append(data['fixtures'][j]['ip'])
                                if data['fixtures'][j].get('port') and data['fixtures'][j]['port'] not in row_data:
                                    row_data.append(data['fixtures'][j]['port'])
                                if data['fixtures'][j].get('brand') and \
                                        f"{data['fixtures'][j]['brand']} {data['fixtures'][j]['model']}" not in row_data:
                                    row_data.append(f"{data['fixtures'][j]['brand']} {data['fixtures'][j]['model']}")
                            elif isinstance(data['fixtures'][j], Router):
                                router_str = str(data['fixtures'][j]).replace('default,', '')
                                if router_str not in row_data:
                                    row_data.append(router_str)
                        except KeyError as e:
                            logging.warning(f"KeyError in fixture processing: {e}")
                            continue  # 继续处理下一个fixture

            temp_data.append(test_name)

            # 添加测试结果和返回值
            if 'result' in data and data['result']:
                row_data.append(data['result'])
            if 'return_value' in data and data['return_value']:
                row_data.extend([*data['return_value']])

        except (KeyError, IndexError) as e:
            logging.error(f"Error processing test result: {e}")
            continue  # 继续处理下一个测试结果

    # 写入最后一行数据
    if row_data:
        with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, quotechar=' ')
            writer.writerow(row_data)

    shutil.copy("pytest.log", "debug.log")
    shutil.move("debug.log", pytest.testResult.logdir)
    # shutil.copy("report.html", "report_bat.html")
    # shutil.move("report_bat.html", pytest.testResult.logdir)
