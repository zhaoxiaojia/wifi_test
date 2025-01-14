# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/25 15:46
# @Author  : chao.li
# @File    : test_demo.py
import time

from dut_control.roku_ctrl import roku_ctrl
from tools.connect_tool.serial_tool import serial_tool
import pytest
import logging

roku = roku_ctrl(pytest.dut.ip)


def test_demo():
    # roku.wifi_conn(ssid='AP-002-5G', pwd='yl12345678.')
    roku.enter_bt()
