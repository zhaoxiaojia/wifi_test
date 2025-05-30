#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: test_demo.py 
@time: 2025/2/12 10:58 
@desc: 
'''
import logging
import time

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from tools.router_tool.Router import Router

'''
Pre step:
1.Set asus router 2.4 Ghz ssid ATC_ASUS_AX88U open system
2.connect asus 

Test step
1.change router 2.4 g
2.change router 5g

Expected Result
'''


@pytest.fixture(autouse=True)
def setup():
    pytest.dut.checkoutput('config_set fw.fastboot.capture.snapshot true')
    pytest.dut.reboot()
    yield


def test_wifi_switch():
    for i in range(1000):
        # 连接wifi
        try:
            pytest.dut.roku.wifi_conn('i-amlogic', '@ml4yourlife')
        except Exception:
            logging.info('wifi connect failed')
        # # 重启
        pytest.dut.reboot()
        # 播放 player
        # Todo
        pytest.dut.roku['837'].launch()
        time.sleep(5)
        pytest.dut.roku.select()
        pytest.dut.checkoutput('cat /sys/class/vdec/vdec_status')
        pytest.dut.checkoutput('cat /proc/asound/card0/pcm*p/sub0/status')
        try:
            pytest.dut.roku.wifi_conn('sunshine','Home1357')
        except Exception:
            logging.info('wifi connect failed')
