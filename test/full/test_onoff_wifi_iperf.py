#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/5 10:23
# @Author  : chao.li
# @Site    :
# @File    : test_onoff_wifi_iperf.py
# @Software: PyCharm



import logging
import os
import time
from test import (Router, close_wifi, connect_ssid, forget_network_cmd, iperf,
                  kill_setting, open_wifi, wait_for_wifi_address)

import pytest

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置

1.连接2.4Gwifi;
2.CH6信道，开关wifi后打流
3.2循环20次。

'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'

router_ch6 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='6', bandwidth='20/40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


ax88uControl = Asusax88uControl()
@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl.change_setting(router_ch6)
    ax88uControl.router_control.driver.quit()
    logging.info(pytest.dut.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
    pytest.dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_change_channel_iperf():
    for _ in range(20):
        close_wifi()
        open_wifi()
        wait_for_wifi_address()
        assert iperf.run_iperf(),"Can't run iperf success"
