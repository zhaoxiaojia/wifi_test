# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/1/12 11:13
# @Author  : chao.li
# @File    : ir.py
# @Project : kpi_test
# @Software: PyCharm
import logging
import time

import pytest


class Ir:
    def __init__(self):
        self.ir = pytest.irsend
        self.ir_name = ''

    def send(self, code, wait_time=0):
        self.ir.send(self.ir_name, code)
        if wait_time:
            time.sleep(wait_time)
