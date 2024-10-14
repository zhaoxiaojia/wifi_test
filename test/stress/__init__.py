# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/12 11:02
# @Author  : chao.li
# @File    : __init__.py.py


import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from tools.connect_tool.adb import ADB

device_list = pytest.config_yaml.get_note('stress_dut')


def multi_stress(func):
    def wrapper(*args, **kwargs):
        with ThreadPoolExecutor(max_workers=len(device_list)) as pool:
            futures = [pool.submit(func, ADB(serialnumber=i)) for i in device_list]
            for j in as_completed(futures):
                j.result()

        # result = func(*args, **kwargs, device_number=device_list)
        return futures

    return wrapper
