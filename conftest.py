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
import shutil

import psutil
import pytest

from tools.connect_tool.adb import ADB
from tools.connect_tool.telnet_tool import TelnetInterface
from tools.TestResult import TestResult

from .tools.yamlTool import yamlTool


def pytest_sessionstart(session):
    '''
    Frame Run Pre-Action Runs only once per frame start
    :param session:
    :return:
    '''
    # The configuration information of  DUT
    pytest.config_yaml = yamlTool(os.getcwd() + '/config/config.yaml')
    # The connection method to the product to DUT
    pytest.connect_type = pytest.config_yaml.get_note('connect_type')['type']
    if pytest.connect_type == 'adb':
        # Create adb obj
        devices_num = pytest.config_yaml.get_note("connect_type")[pytest.connect_type]['device']
        pytest.dut = ADB(serialnumber=devices_num)
        logging.info("adb connected %s" % devices_num)
    elif pytest.connect_type == 'telnet':
        # Create telnet obj
        telnet_ip = pytest.config_yaml.get_note("connect_type")[pytest.connect_type]['ip']
        wildcard = pytest.config_yaml.get_note("connect_type")[pytest.connect_type]['wildcard']
        pytest.dut = TelnetInterface(telnet_ip,wildcard)
        logging.info("telnet connected %s" % telnet_ip)
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


def pytest_sessionfinish(session):
    shutil.copy("pytest.log", "debug.log")
    shutil.move("debug.log", pytest.testResult.logdir)
    shutil.copy("report.html", "report_bat.html")
    shutil.move("report_bat.html", pytest.testResult.logdir)

    if os.path.exists('temp.txt'):
        for proc in psutil.process_iter():
            try:
                files = proc.open_files()
                for f in files:
                    if f.path == 'temp.txt':
                        proc.kill()  # Kill the process that occupies the file
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        os.remove('temp.txt')