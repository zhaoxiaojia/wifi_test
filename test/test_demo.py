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


@pytest.fixture()
def setup_teardown():
    logging.info('This is setup')
    yield
    logging.info('This is teardown')


def test():
    logging.info('This is a demo test')
    assert True
