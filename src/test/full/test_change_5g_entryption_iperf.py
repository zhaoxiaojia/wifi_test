#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/6/6 10:42
# @Author  : chao.li
# @Site    :
# @File    : test_change_5g_entryption_iperf.py
# @Software: PyCharm



import logging
from src.test import (Router, connect_ssid, forget_network_cmd, iperf,
                      kill_setting, wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置

不同加密方式切换打流

1.连接2.4Gwifi;
2.CH6信道，切换不同加密方式，OPEN-WAP1-WAP2-WAP2
3..2循环20次。

TPS正常，无掉零，无断流
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_wpa1 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='36', bandwidth='40 MHz',
                     authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_wpa2 = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='36', bandwidth='40 MHz',
                     authentication_method='WPA3-Personal', wpa_passwd=passwd)
router_open = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='36', bandwidth='40 MHz',
                     authentication_method='Open System', wpa_passwd=passwd)

ax88uControl = Asusax88uControl()


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router

    yield
    ax88uControl.router_control.driver.quit()
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_change_encryption_iperf():
    for i in [router_wpa1, router_wpa2, router_open] * 7:
        ax88uControl.change_setting(i)
        logging.info(pytest.dut.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
        if i.authentication_method == 'Open System':
            pytest.dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT_OPEN.format(ssid))
        else:
            pytest.dut.checkoutput(pytest.dut.CMD_WIFI_CONNECT.format(ssid, 'wpa2', passwd))
        wait_for_wifi_address()
        assert iperf.run_iperf(), "Can't run iperf success"
