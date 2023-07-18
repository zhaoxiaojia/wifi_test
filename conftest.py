#!/usr/bin/env python 
# -*- coding: utf-8 -*- 


"""
# File       : conftest.py
# Time       ：2023/6/29 13:36
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest
from .tools.yamlTool import yamlTool
import os
import logging
from ADB import ADB
from TelnetConnect import TelnetInterface
import time
from tools.TestResult import TestResult
import shutil


def pytest_sessionstart(session):
    '''
    框架运行前置动作 每次框架启动只运行一次
    :param session:
    :return:
    '''
    # 获取 配置信息
    pytest.config_yaml = yamlTool(os.getcwd() + '/config/config_wifi.yaml')
    # 获取 连接方式信息
    pytest.connect_type = pytest.config_yaml.get_note('connect_type')['type']
    if pytest.connect_type == 'usb':
        # 创建 adb 连接 实例
        devices_num = pytest.config_yaml.get_note("connect_type")[pytest.connect_type]['device']
        pytest.executer = ADB(serialnumber=devices_num)
        logging.info("adb connected %s" % devices_num)
    elif pytest.connect_type == 'telnet':
        # 创建 serial 连接 实例
        telnet_ip = pytest.config_yaml.get_note("connect_type")[pytest.connect_type]['ip']
        pytest.executer = TelnetInterface(telnet_ip)
        logging.info("telnet connected %s" % telnet_ip)
    else:
        raise EnvironmentError("Not support connect type %s" % pytest.connect_type)
    pytest.executer.root()
    pytest.executer.remount()


    # 创建 测试结果文件夹
    result_path = os.path.join(os.getcwd(), 'results\\' + time.asctime().replace(' ', '_').replace(':', '_'))
    os.mkdir(result_path)
    pytest.testResult = TestResult(result_path, [])


def pytest_sessionfinish(session):
    shutil.copy("pytest.debug.log", "debug.log")
    shutil.move("debug.log", pytest.testResult.logdir)
    if os.path.exists('temp.txt'):
        os.remove('temp.txt')
