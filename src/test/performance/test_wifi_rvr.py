# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
File       : test_wifi_rvr.py
Time       ：2023/9/15 14:03
Author     ：chao.li
version    ：python 3.9
Description：
"""

import logging
import time
from src.test import get_testdata
import pytest

from src.tools.router_tool.router_factory import get_router
from src.tools.config_loader import load_config

from src.test.performance import common_setup, init_rf

test_data = get_testdata(get_router(load_config(refresh=True)['router']['name']))


@pytest.fixture(scope='session', params=test_data, ids=[str(i) for i in test_data])
def setup_router(request):
    rf_step_list = []
    rf_tool = None

    def pre(cfg, _router):
        nonlocal rf_tool, rf_step_list
        rf_tool, rf_step_list = init_rf(cfg)

    common = common_setup(request, pre_setup=pre)
    connect_status, router_info, _, _ = next(common)
    try:
        yield connect_status, router_info, rf_step_list, rf_tool
    finally:
        next(common, None)
        logging.info('Reset rf value')
        rf_tool.execute_rf_cmd(0)
        logging.info(rf_tool.get_rf_current_value())
        time.sleep(10)


def test_rvr(setup):
    connect_status, router_info, rf_step_list, rf_tool = setup
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write("\n Can't connect wifi , skip this loop\n\n")
        return
    for rf_value in rf_step_list:
        logging.info(f'set rf value {rf_value}')
        db_set = rf_value[1] if isinstance(rf_value, tuple) else rf_value
        rf_tool.execute_rf_cmd(db_set)
        logging.info(rf_tool.get_rf_current_value())
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write('-' * 40 + '\n')
            info = ''
            info += 'db_set : ' + str(db_set) + '\n'
            info += 'corner_set : \n'
            f.write(info)

        pytest.dut.get_rssi()
        logging.info('start test iperf')
        if int(router_info.rx):
            logging.info(f'rssi : {pytest.dut.rssi_num}')
            pytest.dut.get_tx_rate(router_info, 'TCP', db_set=db_set)
        if int(router_info.tx):
            logging.info(f'rssi : {pytest.dut.rssi_num}')
            pytest.dut.get_rx_rate(router_info, 'TCP', db_set=db_set)
