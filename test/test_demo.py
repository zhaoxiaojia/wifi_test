# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/25 15:46
# @Author  : chao.li
# @File    : test_demo.py


import pytest


@pytest.fixture(autouse=True)
def power():
    return "192.168.50.1", '2'


@pytest.fixture(autouse=True)
def router(power):
    print(power)


def test():
    print("There is nothing")
