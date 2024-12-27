# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/25 15:46
# @Author  : chao.li
# @File    : test_demo.py

import itertools
import logging
import time

import pytest

bt_device = 'JBL GO 2'


@pytest.fixture(params=['xiaomi'],autouse=True)
def setup_teardown(request):
    logging.info('This is setup')
    logging.info(f'request.param {request.param}')
    yield
    logging.info('This is teardown')


@pytest.mark.parametrize("rf_value", [1,2])
def test(rf_value):
    logging.info('This is a demo test')
    logging.info(f'rf_value {rf_value}')
    assert True
