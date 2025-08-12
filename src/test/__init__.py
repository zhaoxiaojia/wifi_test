import csv
import logging
import os

import pytest
from src.tools.router_tool.Router import Router
from src.tools.config_loader import load_config
from src.util.constants import get_config_base

config_yaml = load_config()

def get_testdata(router):
    config_base = get_config_base()
    router_name = config_yaml.get('router')['name']
    base = config_base / "performance_test_csv"
    if "asus" in router_name:
        csv_path = base / "asus" / "rvr_wifi_setup.csv"
    elif "xiaomi" in router_name:
        csv_path = base / "xiaomi" / "rvr_wifi_setup.csv"
    else:
        csv_path = config_base / "rvr_wifi_setup.csv"

    print(f"router_name: {router_name}, csv_path: {csv_path}")
    pc_ip, dut_ip = "", ""
    # 读取 测试配置
    test_data = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)

            for i in [j for j in reader][1:]:
                if not i:
                    continue
                stripped_i = [field.strip() for field in i]
                test_data.append(Router(*stripped_i))
    except FileNotFoundError:
        raise FileNotFoundError(
            f"CSV file not found at {csv_path}. Please check router name '{router_name}'."
        )
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
        assert i.wireless_mode in {'2.4 GHz': router.WIRELESS_2, '5 GHz': router.WIRELESS_5}[
            i.band], "Pls check wireless info"
        assert i.channel in {'2.4 GHz': router.CHANNEL_2, '5 GHz': router.CHANNEL_5}[
            i.band], "Pls check channel info"
        assert i.bandwidth in {'2.4 GHz': router.BANDWIDTH_2, '5 GHz': router.BANDWIDTH_5}[
            i.band], "Pls check bandwidth info"
        if 'Legacy' in i.wireless_mode:
            assert i.authentication in router.AUTHENTICATION_METHOD_LEGCY, "Pls check authentication info"
        else:
            assert i.authentication in router.AUTHENTICATION_METHOD, "Pls check authentication info"
    return test_data
