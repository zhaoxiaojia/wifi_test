import csv
import logging
import os
import re
import subprocess

import psutil
import pytest

from tools.connect_tool.adb import accompanying_dut
from tools.playback_tool.Youtube import Youtube
from tools.router_tool.Router import Router
from tools.yamlTool import yamlTool

# if pytest.connect_type == 'adb':
#     Router = Router
#     add_network = pytest.dut.add_network
#     enter_wifi_activity = pytest.dut.enter_wifi_activity
#     forget_network_cmd = pytest.dut.forget_wifi
#     kill_setting = pytest.dut.kill_setting
#     wait_for_wifi_address = pytest.dut.wait_for_wifi_address
#     connect_ssid = pytest.dut.connect_ssid
#     close_wifi = pytest.dut.close_wifi
#     open_wifi = pytest.dut.open_wifi
#     find_ssid = pytest.dut.find_ssid
#     wait_keyboard = pytest.dut.wait_keyboard
#     close_hotspot = pytest.dut.close_hotspot
#     open_hotspot = pytest.dut.open_hotspot
#     kill_moresetting = pytest.dut.kill_moresetting
#     accompanying_dut = accompanying_dut
#     wait_for_wifi_service = pytest.dut.wait_for_wifi_service
#     change_keyboard_language = pytest.dut.change_keyboard_language
#     reset_keyboard_language = pytest.dut.reset_keyboard_language
#     connect_save_ssid = pytest.dut.connect_save_ssid
#     get_hwaddr = pytest.dut.get_hwaddr
#     wait_router = pytest.dut.wait_router
#     forget_ssid = pytest.dut.forget_ssid
#
#     youtube = Youtube()
#     iperf = Iperf()
#
#     open_info = r'<node index="0" text="Hotspot name" resource-id="android:id/title" class="android.widget.TextView" package="com.(.*?).tv.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="true"'
#     close_info = r'<node index="0" text="Hotspot name" resource-id="android:id/title" class="android.widget.TextView" package="com.(.*?).tv.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="false"'
#     wifi_onoff_tag = 'Available networks'
#
#     config_yaml = pytest.config_yaml


def get_testdata(router):
    wifi_yaml = yamlTool(os.getcwd() + '/config/config.yaml')
    router_name = wifi_yaml.get_note('router')['name']
    pc_ip, dut_ip = "", ""

    # 读取 测试配置
    with open(os.getcwd() + '/config/rvr_wifi_setup.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        test_data = [Router(*[i.strip() for i in row]) for row in reader][1:]

    # logging.info(f'test_data {test_data}')
    ssid_verify = set()

    # 校验 csv 数据是否异常
    for i in test_data:
        logging.info(i)
        if pytest.connect_type != 'adb':
            break
        if '2' in i.band:
            ssid_verify.add(i.ssid)
        if '5' in i.band:
            assert i.ssid not in ssid_verify, "5g ssid can't as the same as 2g , pls modify"
        assert i.band in ['2.4 GHz', '5 GHz'], "Pls check band info "
        assert i.wireless_mode in {'2.4 GHz': router.WIRELESS_2_MODE, '5 GHz': router.WIRELESS_5_MODE}[
            i.band], "Pls check wireless info"
        assert i.channel in {'2.4 GHz': router.CHANNEL_2, '5 GHz': router.CHANNEL_5}[
            i.band], "Pls check channel info"
        assert i.bandwidth in {'2.4 GHz': router.BANDWIDTH_2, '5 GHz': router.BANDWIDTH_5}[
            i.band], "Pls check bandwidth info"
        if 'Legacy' in i.wireless_mode:
            assert i.authentication_method in router.AUTHENTICATION_METHOD_LEGCY, "Pls check authentication info"
        else:
            assert i.authentication_method in router.AUTHENTICATION_METHOD, "Pls check authentication info"
    return test_data





