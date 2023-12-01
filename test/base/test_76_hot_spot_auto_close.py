#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_76_hot_spot_auto_close.py
# Time       ：2023/7/18 10:20
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging
import re
import time

import pytest

'''
测试步骤
1.开启热点
2.开启“自动关闭SAP没有STA连接时”，没有任何设备连接SAP，等待15分钟
'''

@pytest.fixture(autouse=True)
def setup_teardown():
    pytest.executer.open_hotspot()
    logging.info('setup done')
    yield
    pytest.executer.kill_moresetting()

@pytest.mark.hot_spot
def test_hotspot_auto_close():
    time.sleep(60*10)
    pytest.executer.uiautomator_dump()
    assert re.findall(pytest.executer.CLOSE_INFO,pytest.executer.get_dump_info(),re.S),"hotspot doesn't be closed"