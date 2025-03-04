#!/usr/bin/env python 
# -*- coding: utf-8 -*-
"""
# File       : conftest.py
# Time       ：2023/6/29 13:36
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import datetime
import logging
import os
import re
import shutil
import subprocess
import sys

import psutil
import pytest
import csv
from tools.connect_tool.adb import adb
from tools.connect_tool.host_os import host_os
from tools.connect_tool.telnet_tool import telnet_tool
from tools.TestResult import TestResult
from tools.yamlTool import yamlTool
from dut_control.roku_ctrl import roku_ctrl

# pytest_plugins = "util.report_plugin"
test_results = []


def pytest_sessionstart(session):
    '''
    Frame Run Pre-Action Runs only once per frame start
    :param session:
    :return:
    '''
    # get host os
    pytest.host_os = host_os()
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
        wildcard = pytest.config_yaml.get_note("connect_type")[pytest.connect_type]['wildcard']
        pytest.dut = telnet_tool(telnet_ip, wildcard)
        pytest.dut.roku = roku_ctrl(telnet_ip)
    else:
        raise EnvironmentError("Not support connect type %s" % pytest.connect_type)

    # Create a test results folder
    if not os.path.exists('results'):
        os.mkdir('results')
    pytest.timestamp = session.config.getoption("--resultpath")
    pytest.result_path = os.getcwd() + '/report/' + pytest.timestamp
    pytest.testResult = TestResult(pytest.result_path, [])
    if os.path.exists('temp.txt'):
        os.remove('temp.txt')


def pytest_addoption(parser):
    parser.addoption("--resultpath", action="store", default=None, help="Test result path")
    parser.addoption("--linux-only", action="store_true")


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
    flag = config.getoption("--linux-only")
    for item in items:
        item.name = item.name.encode("utf-8").decode("unicode-escape")
        item._nodeid = item._nodeid.encode("utf-8").decode("unicode-escape")
        func = item.function
        if flag:
            if not (func.__doc__ and "#linux" in func.__doc__):
                continue
            new_items.append(item)
    if flag: items[:] = new_items


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    获取测试返回值，并存入 request.node._store['return_value']
    """
    outcome = yield
    report = outcome.get_result()
    if report.when == 'call':
        item._store['test_result'] = "PASSED" if report.passed else "FAILED"
        logging.info(f"item {item._store['test_result']}")
        # 记录返回值
        if not report.failed:
            return_value = getattr(call, "result", None) or item._store.get("return_value", None)
            logging.info(f'record return value: {call.result}')
            item._store["return_value"] = return_value


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    csv_file = "test_results.csv"

    # 生成表头
    row_data = []
    logging.info(test_results)
    for test_result in test_results:
        test_name = sorted(test_result.keys())[0]
        if test_name in row_data:
            with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
                writer = csv.writer(file, quotechar=' ')
                writer.writerow(row_data)  # 写入数据
            row_data.clear()
        data = test_result[test_name]
        keys = sorted(data['fixtures'].keys())
        if data['fixtures'][keys[0]] not in row_data:
            for j in keys:
                row_data.append(data['fixtures'][j])
        row_data.append(test_name)
        row_data.append(data['result'])
        row_data.append(data['return_value'])
    with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, quotechar=' ')
        writer.writerow(row_data)

    shutil.copy("pytest.log", "debug.log")
    shutil.move("debug.log", pytest.testResult.logdir)
    # shutil.copy("report.html", "report_bat.html")
    # shutil.move("report_bat.html", pytest.testResult.logdir)
