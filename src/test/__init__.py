import csv
import logging
import os

import pytest

from src.tools.router_tool.Router import Router
from src.tools.yamlTool import yamlTool


def get_testdata(router):
    wifi_yaml = yamlTool(os.getcwd() + '/config/config.yaml')
    router_name = wifi_yaml.get_note('router')['name']
    pc_ip, dut_ip = "", ""
    # 读取 测试配置
    test_data = []
    with open(os.getcwd() + '/config/rvr_wifi_setup.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)

        for i in  [j for j in reader][1:]:
            if not i:
                continue
            stripped_i = [field.strip() for field in i]
            test_data.append(Router(*stripped_i))
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
        assert i.wireless_mode  in {'2.4 GHz': router.WIRELESS_2, '5 GHz': router.WIRELESS_5}[
            i.band], "Pls check wireless info"
        assert i.channel  in {'2.4 GHz': router.CHANNEL_2, '5 GHz': router.CHANNEL_5}[
            i.band], "Pls check channel info"
        assert i.bandwidth  in {'2.4 GHz': router.BANDWIDTH_2, '5 GHz': router.BANDWIDTH_5}[
            i.band], "Pls check bandwidth info"
        if 'Legacy' in i.wireless_mode:
            assert i.authentication  in router.AUTHENTICATION_METHOD_LEGCY, "Pls check authentication info"
        else:
            assert i.authentication  in router.AUTHENTICATION_METHOD, "Pls check authentication info"
    return test_data




