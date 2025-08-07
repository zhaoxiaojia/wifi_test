#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/5/30 10:27
# @Author  : chao.li
# @Site    :
# @File    : test_add_network_check_info.py
# @Software: PyCharm


from src.test import (Router, add_network, enter_wifi_activity, forget_network_cmd,
                      kill_setting, wait_for_wifi_address)

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

'''
测试配置
添加WIFI网络·

Open加密方式

添加安全性选择 加密方式-开放的网络

能添加成功
'''

ssid = 'ATC_ASUS_AX88U_5G'
router_2g = Router(band='5 GHz', ssid=ssid, wireless_mode='自动', channel='157', bandwidth='80 MHz',
                   authentication='Open System')


@pytest.fixture(scope='function', autouse=True)
def setup():
    # set router
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_2g)
    ax88uControl.router_control.driver.quit()
    yield
    kill_setting()
    forget_network_cmd(target_ip='192.168.50.1',ssid=ssid)


def test_add_network_open():
    add_network(ssid, 'None')
    assert wait_for_wifi_address(), "Connect fail"
    enter_wifi_activity()
    pytest.dut.uiautomator_dump()
    assert ssid in pytest.dut.get_dump_info(),"Can't display ssid info "
