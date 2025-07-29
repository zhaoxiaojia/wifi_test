#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/3/31 16:40
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_smart_connect_reboot.py
# @Software: PyCharm


from src.test import Router, connect_ssid, forget_network_cmd, kill_setting

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试步骤
1.AP 5G和2.4G设置相同的SSID和密码类型以及密码；
2.DUT连接AP（强信号）；
3.Reboot DUT 检查回连

默认连接5G
'''

ssid_name = 'ATC_ASUS_AX88U'
passwd = 'test1234'
router = Router(band='2.4 GHz', ssid=ssid_name, wireless_mode='Legacy', channel='自动', bandwidth='20 MHz',
                authentication_method='WPA2-Personal', wpa_passwd=passwd,
                smart_connect=True)


@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router)
    ax88uControl.router_control.driver.quit()
    yield
    forget_network_cmd(target_ip='192.168.50.1')
    kill_setting()


def test_smart_connect():
    assert connect_ssid(ssid_name, passwd), "Can't connect"
    assert pytest.dut.ping(hostname="192.168.50.1"), "Can't ping"
    assert 'freq: 5' in pytest.dut.checkoutput(pytest.dut.IW_LINNK_COMMAND), "Doesn't conect 5g "
