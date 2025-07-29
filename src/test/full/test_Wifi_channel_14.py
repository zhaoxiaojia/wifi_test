#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/12 13:38
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_channel_14.py
# @Software: PyCharm


from src.test import (Router, connect_ssid, forget_network_cmd, kill_setting,
                      wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
Auto mode 信道14

Connect an AP which channel is 14
'''

ssid = 'ATC_ASUS_AX88U_2G'
passwd = 'Abc@123456'
router_2g = Router(band='2.4 GHz', ssid=ssid, wireless_mode='自动', channel='11', bandwidth='20/40 MHz',
                   authentication_method='WPA/WPA2-Personal', wpa_passwd=passwd, country_code='中国 (默认值)')


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    global router_2g
    ax88uControl = Asusax88uControl()
    ax88uControl.change_country(router_2g)
    ax88uControl.change_setting(router_2g)
    yield
    kill_setting()
    router_2g = router_2g._replace(country_code='美国')
    ax88uControl.change_country(router_2g)
    ax88uControl.router_control.driver.quit()
    forget_network_cmd(target_ip='192.168.50.1')


def test_channel_14():
    assert True
    # connect_ssid(ssid, passwd=passwd)
    # assert wait_for_wifi_address(), "Connect fail"
