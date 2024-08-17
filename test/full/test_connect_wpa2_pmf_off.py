# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_connect_wpa2_pmf_off.py
# Time       ：2023/7/31 17:23
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
PMF 关闭 WPA2加密

１.AP set PMF PMF关闭，and secutiy WPA2;
2.DUT connect ap and play online video.

连接成功
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = '12345678'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='1', bandwidth='20 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd,protect_frame='停用')



@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    pytest.executer.kill_setting()
    pytest.executer.forget_network_cmd(target_ip='192.168.50.1')

@pytest.mark.wifi_connect
def test_connect_wpa2():
    assert pytest.executer.connect_ssid(ssid, passwd),"Can't connect"
    assert pytest.executer.wait_for_wifi_address(), "Connect fail"


