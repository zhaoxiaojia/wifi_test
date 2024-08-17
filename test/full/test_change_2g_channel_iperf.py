#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : test_change_2g_channel_iperf.py
# Time       ：2023/7/24 15:30
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
1.连接2.4Gwifi;
2.切换不同信道进行打流，1-6-11
3.循环20次。
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
iperf = Iperf()
@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router

    yield
    ax88uControl.router_control.driver.quit()
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')


def test_change_channel_iperf():
    for i in [router_ch1,router_ch6,router_ch11]* 7:
        ax88uControl.change_setting(i)
        logging.info(pytest.executer.CMD_WIFI_CONNECT.format(ssid,'wpa2',passwd))
        pytest.executer.checkoutput(pytest.executer.CMD_WIFI_CONNECT.format(ssid,'wpa2',passwd))
        pytest.executer.wait_for_wifi_address()
        assert iperf.run_iperf(),"Can't run iperf success"
