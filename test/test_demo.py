# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/25 15:46
# @Author  : chao.li
# @File    : test_demo.py
import logging

import pytest


@pytest.fixture(autouse=True)
def router_setting():
    return 'router_setting'


def test_addition(router_setting):
    result = 2 + 3
    logging.info(router_setting)
    assert result == 5
    return result  # 确保 pytest 能够捕获 return 值


def test_subtraction(router_setting):
    result = 10 - 5
    logging.info(router_setting)
    assert result == 5
    return result


@pytest.mark.skip(reason="Skipping this test")
def test_skipped_case():
    result = "This test is skipped"
    return result
