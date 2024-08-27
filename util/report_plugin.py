# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/27 14:43
# @Author  : chao.li
# @File    : report_plugin.py

import logging

pytest_plugins = "util.report_plugin"


def pytest_runtest_call(__multicall__):
    try:
        logging.info('Can I see this?')
        __multicall__.execute()
    except Exception as e:
        logging.exception(e)
        raise
