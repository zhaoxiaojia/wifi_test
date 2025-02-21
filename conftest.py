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

from tools.connect_tool.adb import adb
from tools.connect_tool.host_os import host_os
from tools.connect_tool.telnet_tool import telnet_tool
from tools.TestResult import TestResult

from .tools.yamlTool import yamlTool

pytest_plugins = "util.report_plugin"


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
    parser.addoption(
        "--resultpath", action="store", default=None, help="Test result path"
    )


def pytest_runtest_logreport(report):
    if report.when == "setup" and hasattr(report, "nodeid"):
        test_nodeid = report.nodeid
        if "[" in test_nodeid:
            params = test_nodeid.split("[", 1)[-1].rstrip("]")
            logging.info('*'*80)
            logging.info(f"* Test params: {params}")
            logging.info('*' * 80)

def pytest_collection_modifyitems(items):
    # item表示收集到的测试用例，对他进行重新编码处理
    for item in items:
        item.name = item.name.encode("utf-8").decode("unicode-escape")
        item._nodeid = item._nodeid.encode("utf-8").decode("unicode-escape")

def pytest_sessionfinish(session):
    shutil.copy("pytest.log", "debug.log")
    shutil.move("debug.log", pytest.testResult.logdir)
    shutil.copy("report.html", "report_bat.html")
    shutil.move("report_bat.html", pytest.testResult.logdir)
