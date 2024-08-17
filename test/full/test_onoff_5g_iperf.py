#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_onoff_5g_iperf.py
# Time       ：2023/7/25 9:12
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import logging

import pytest

from tools.Iperf import Iperf
from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置

1.连接5Gwifi;
2.CH36信道，开关wifi后打流
3.2循环20次。

'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'

router_ch6 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='36', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


ax88uControl = Asusax88uControl()
iperf = Iperf()
@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl.change_setting(router_ch6)
    ax88uControl.router_control.driver.quit()
    logging.info(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
    pytest.executer.checkoutput(pytest.executer.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


def test_onoff_wifi_iperf():
    for _ in range(20):
        pytest.executer.close_wifi()
        pytest.executer.open_wifi()
        pytest.executer.wait_for_wifi_address()
        assert iperf.run_iperf(),"Can't run iperf success"
