#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: test_demo.py 
@time: 2025/2/12 10:58 
@desc: 
'''


import logging
import time

import pytest

from dut_control.roku_ctrl import roku_ctrl
from tools.connect_tool.serial_tool import serial_tool

roku = roku_ctrl(pytest.dut.ip)


def test_demo():
    roku.wifi_conn(ssid='AP-002-5G', pwd='yl12345678.')
    roku.enter_bt()
