#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/4/20 10:33
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_change_to_another_ap.py
# @Software: PyCharm


import re
import time
from src.test import Router, connect_ssid, forget_network_cmd, kill_setting

import pytest

from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.ZTEax5400Control import ZTEax5400Control

'''
测试步骤
1.连接AP1；
2.连接另外一个AP2

输入正确的密码后开始连接，平台能自动断开与AP1的连接，而连接上AP2.
'''


asus_ssid_name = 'ATC_ASUS_AX88U'
zte_ssid_name = 'ZTEax5400_5G'
passwd = 'test1234'
router_ausu = Router(band='2.4 GHz', ssid=asus_ssid_name, wireless_mode='自动', channel='自动', bandwidth='20 MHz',
                   authentication='WPA2-Personal', wpa_passwd=passwd)
router_zte = Router(band='5 GHz', ssid=zte_ssid_name, wireless_mode='802.11 a/n/ac', channel='161', bandwidth='20MHz/40MHz/80MHz',
                   authentication='WPA-PSK/WPA2-PSK', wpa_passwd=passwd)





check_top_info = r'content-desc="ZTEax5400_5G.*?\[1200,359\]\[1920,498\]">'
check_save_info = 'content-desc="ATC_ASUS_AX88U,Saved'
@pytest.fixture(autouse=True)
def setup_teardown():
    ax88uControl = Asusax88uControl()
    ax88uControl.change_setting(router_ausu)
    ax88uControl.router_control.driver.quit()
    time.sleep(3)
    zte5400Control = ZTEax5400Control()
    zte5400Control.change_setting(router_zte)
    zte5400Control.router_control.driver.quit()
    yield
    forget_network_cmd(target_ip='192.168.50.1')
    forget_network_cmd(target_ip='192.168.2.1')
    kill_setting()


def test_change_ap():
    connect_ssid(asus_ssid_name, passwd)
    kill_setting()
    connect_ssid(zte_ssid_name,passwd)
    pytest.dut.wait_element('NetWork & Internet','text')
    dumpinfo = pytest.dut.get_dump_info()
    assert re.findall(check_top_info,dumpinfo,re.S),'Connect ssid not on the top'
    assert check_save_info in dumpinfo, 'Last ssid not saved'