# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/25 15:46
# @Author  : chao.li
# @File    : test_demo.py


from dut_control.roku_ctrl import roku_ctrl
import pytest

roku = roku_ctrl()


def test_demo():
    assert roku.wifi_conn(ssid='AP-002-2.4G')
