# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/12 11:02
# @Author  : chao.li
# @File    : __init__.py.py


import logging
import threading
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
import re
from tools.connect_tool.adb import adb

info = subprocess.check_output("adb devices", shell=True, encoding='utf-8')
device_list = re.findall(r'\n(.*?)\s+device', info, re.S)
logging.info(device_list)


def multi_stress(func):
    def wrapper(*args, **kwargs):
        with ThreadPoolExecutor(max_workers=len(device_list)) as pool:
            futures = [pool.submit(func, adb(serialnumber=i)) for i in device_list]
            for j in as_completed(futures):
                j.result()

        # result = func(*args, **kwargs, device_number=device_list)
        return futures

    return wrapper
