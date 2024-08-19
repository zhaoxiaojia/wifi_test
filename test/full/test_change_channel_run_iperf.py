# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/25 15:11
# @Author  : Chao.li
# @File    : test_change_channel_run_iperf.py
# @Project : python
# @Software: PyCharm



import logging
import os
import time

import pytest
from test import (Router, connect_ssid, forget_network_cmd, iperf,
                        kill_setting, wait_for_wifi_address)

from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
Auto 2.4G

Connect an AP which wireless mode is Auto+2.4G

Platform connect the AP successful
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_ch1 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20/40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_ch6 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='6', bandwidth='20/40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)
router_ch11 = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='11', bandwidth='20/40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


ax88uControl = Asusax88uControl()
@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router

    yield
    ax88uControl.router_control.driver.quit()
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1')


def test_change_channel_iperf():
    for i in [router_ch1,router_ch6,router_ch11]*7:
        ax88uControl.change_setting(i)
        logging.info(pytest.executer.CMD_WIFI_CONNECT.format(ssid,'wpa2',passwd))
        pytest.executer.checkoutput(pytest.executer.CMD_WIFI_CONNECT.format(ssid,'wpa2',passwd))
        wait_for_wifi_address()
        assert iperf.run_iperf(),"Can't run iperf success"
