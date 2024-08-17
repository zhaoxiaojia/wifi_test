# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_reboot_dut.py
# Time       ：2023/8/2 10:18
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import pytest

from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
连接AC-5G
AC on/off DUT

1.AC on/off DUT
2.Play online video.

1.WiFi will auto reconnected
2.Can play online video
'''

ssid = 'ATC_ASUS_AX88U_5G'
passwd = 'Abc@123456'
router_5g = Router(band='5 GHz', ssid=ssid, wireless_mode='N/AC/AX mixed', channel='165', bandwidth='40 MHz',
                   authentication_method='WPA2-Personal', wpa_passwd=passwd)


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_5g)
    ax88uControl.router_control.driver.quit()
    yield
    # kill_tvsetting()
    # forget_network_cmd(target_ip='192.168.50.1')

@pytest.mark.reset_dut
def test_reopen_dut():
    pytest.executer.connect_ssid(ssid,passwd)
    pytest.executer.playback_youtube()
    pytest.executer.reboot()
    pytest.executer.wait_for_wifi_service()
    pytest.executer.playback_youtube()


