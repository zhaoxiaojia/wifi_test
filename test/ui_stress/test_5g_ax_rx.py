# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_5g_ax_rx.py
# Time       ：2023/9/14 10:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import time

import pytest

from tools.Iperf import Iperf
from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
5G-TX

1.连接5g网络
3.配合终端A
4.tps 测试 rX

TPS正常，无掉零
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'

router = Router(band='5 GHz', ssid=ssid, wireless_mode='AX only', channel='36', bandwidth='40 MHz',
                authentication_method='WPA2-Personal', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()
iperf = Iperf()


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl.change_setting(router)
    ax88uControl.router_control.driver.quit()
    time.sleep(3)
    pytest.dut.connect_ssid(ssid, passwd)
    logging.info('setup done')
    yield
    pytest.dut.home()
    pytest.dut.forget_ssid(ssid)
    pytest.dut.IPERF_TEST_TIME = 30
    pytest.dut.IPERF_WAIT_TIME = pytest.dut.IPERF_TEST_TIME * 2


@pytest.mark.hot_spot
def test_5g_iperf_rx():
    pytest.dut.IPERF_TEST_TIME = 3600 * 24
    pytest.dut.IPERF_WAIT_TIME = pytest.dut.IPERF_TEST_TIME + 20
    iperf.run_iperf(type='rx')
