# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/14 11:20
# @Author  : chao.li
# @File    : test_monkey.py


import time
from src.test.stress import multi_stress

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.Router import Router

ssid_2g = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid_2g, wireless_mode='11n', channel='1', bandwidth='40 MHz',
                   authentication='Open System')

'''
Test step
1.Monkey test, input command "logcat -v threadtime >/sdcard/mk.log & monkey 
--ignore-timeouts --ignore-crashes --kill-process-after-error --throttle 1000 -v -v -v 999999" in secueCRT.

Expected Result
The device works well,and wifi is ok.

'''

monkey_cmd = ("logcat -v threadtime >/sdcard/mk.log & monkey --ignore-timeouts "
              "--ignore-crashes --kill-process-after-error --throttle 1000 -v -v -v 999999")

@pytest.mark.wifi_connect
@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    time.sleep(10)
    yield
    pytest.dut.forget_network_cmd(target_ip='192.168.50.1')
    pytest.dut.kill_setting()


@multi_stress
def test_monkey(device):
    device.checkoutput(monkey_cmd)