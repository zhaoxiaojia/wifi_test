# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/25 15:46
# @Author  : chao.li
# @File    : test_demo.py
import logging

import pytest


def test_multi_throughtput_rx():
    rssi_num = pytest.dut.get_rssi()
    rx_result = pytest.dut.get_rx_rate(router_setting, rssi_num)