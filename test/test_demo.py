# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/25 15:46
# @Author  : chao.li
# @File    : test_demo.py
import logging
import pytest
import itertools

params = list(itertools.product(['xiaomi3000', 'asus88u'], ['tx', 'rx']))

ids = [f"Test_compatibility_{i[0]+1} {i[1][0]}" for i in enumerate(params)]


@pytest.fixture(autouse=True, params=params, ids=ids)
def wifi_setup_teardown(request):
    router = request.param[0]
    logging.info(f"Set {router}")
    return request.param[1]


def test(wifi_setup_teardown):
    logging.info(f"This is test {wifi_setup_teardown}")

