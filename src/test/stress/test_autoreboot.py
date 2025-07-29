# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/14 9:57
# @Author  : chao.li
# @File    : test_autoreboot.py


import time
import pytest

from src.tools.router_tool.Router import Router

ssid_2g = 'ATC_ASUS_AX88U_2G'
router_2g = Router(band='2.4 GHz', ssid=ssid_2g, wireless_mode='N only', channel='1', bandwidth='40 MHz',
                   authentication_method='Open System')

'''
Test step
1.Connect any AP
2.Do autoreboot stress test for about 12 hours.
3.Check wifi status

Expected Result
3.WIFI works well,AP list display normal.

'''
#ser = serial_tool('COM48', 921600)
# 开始检测关键字
#keyword = "[AML_SDIO] W1 Chip type(1:2:0)"
#ser.start_keyword_detection(keyword)

@pytest.mark.wifi_connect
@pytest.fixture(autouse=True)
def setup_teardown():
    # ax88uControl = Asusax86uControl()
    # ax88uControl.change_setting(router_2g)
    # ax88uControl.router_control.driver.quit()
    # time.sleep(10)
    yield
    # pytest.dut.forget_network_cmd(target_ip='10.18.18.')
    # pytest.dut.kill_setting()


# @multi_stress
# def test_autoreboot(device):
#     time.sleep(10)
#     while True:
#         if ser.is_keyword_detected(keyword):
#             print(f"在 kernel log 中找到了关键字 '{keyword}'")
#             break
#         time.sleep(0.1)  # 短暂休眠减少CPU占用
#         device.checkoutput(device.CMD_WIFI_CONNECT.format(ssid_2g, 'open', ''))
#         device.wait_for_wifi_address(target="10.18.18.")
#         device.reboot()
#         device.wait_for_wifi_address(target="10.18.18.")

def test_autoreboot(device):
    start_time = time.time()
    while time.time() - start_time < 3600 * 12:
        device.checkoutput(device.CMD_WIFI_CONNECT.format(ssid_2g, 'open', ''))
        device.wait_for_wifi_address(target="10.18.18.")
        device.reboot()
        device.wait_for_wifi_address(target="10.18.18.")