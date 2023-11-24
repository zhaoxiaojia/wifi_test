# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_ctcc_stress.py
# Time       ：2023/11/22 13:40
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest
from . import Iptv_ctl,videoLink

iptvCtl = Iptv_ctl()

bt_test = False
@pytest.fixture(autouse=True)
def setuo_teardown():
    if bt_test:
        iptvCtl.init_ser()
        iptvCtl.bt_device_press()
        iptvCtl.connect_bt("MI BT18")
    yield
    if bt_test:
        iptvCtl.cancel_bt("MI BT18")
        iptvCtl.bt_device_press()
    pytest.executer.home()


def test_ctcc():
    iptvCtl.connect_wifi("AX86U-5G","12345678")
    for i in videoLink:
        iptvCtl.play_exo(i.value)