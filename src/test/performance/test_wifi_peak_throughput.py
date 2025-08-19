# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
File       : test_wifi_peak_throughput.py
Time       ：2023/9/15 14:03
Author     ：chao.li
version    ：python 3.9
Description：
"""

import logging
from src.test import get_testdata
import pytest

from src.tools.router_tool.router_factory import get_router
from src.tools.config_loader import load_config

from src.test.performance import common_setup

router_name = load_config(refresh=True)['router']['name']
router = get_router(router_name)
logging.info(f'router {router}')
test_data = get_testdata(router)

step_list = [0]


@pytest.fixture(scope='session', params=test_data, ids=[str(i) for i in test_data])
def setup_router(request):
    common = common_setup(request)
    connect_status, router_info, _, _ = next(common)
    try:
        yield connect_status, router_info
    finally:
        next(common, None)


@pytest.mark.parametrize("rf_value", step_list)
def test_rvr(setup, rf_value):
    if not setup[0]:
        logging.info("Can't connect wifi ,input 0")
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write("\n Can't connect wifi , skip this loop\n\n")
        return
    router_info = setup[1]

    logging.info(f'rf_value {rf_value}')

    with open(pytest.testResult.detail_file, 'a') as f:
        f.write('-' * 40 + '\n')
        info = ''
        db_set = 0
        info += 'db_set : \n'
        info += 'corner_set : \n'
        f.write(info)

    pytest.dut.get_rssi()
    logging.info('start test tx/rx')
    if int(router_info.tx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_tx_rate(router_info, 'TCP', db_set=db_set)
    if int(router_info.rx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_rx_rate(router_info, 'TCP', db_set=db_set)
