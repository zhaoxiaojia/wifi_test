# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
File       : test_wifi_rvo.py
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

from src.test.performance import common_setup, init_corner

router_name = load_config(refresh=True)['router']['name']
router = get_router(router_name)
logging.info(f'router {router}')
test_data = get_testdata(router)


@pytest.fixture(scope='session', params=test_data, ids=[str(i) for i in test_data])
def setup_router(request):
    corner_step_list = []
    corner_tool = None

    def pre(cfg, _router):
        nonlocal corner_tool, corner_step_list
        corner_tool, corner_step_list = init_corner(cfg)

    common = common_setup(request, pre_setup=pre)
    connect_status, router_info, _, _ = next(common)
    try:
        yield connect_status, router_info, corner_step_list, corner_tool
    finally:
        next(common, None)


def test_rvr(setup):
    connect_status, router_info, corner_step_list, corner_tool = setup
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write("\n Can't connect wifi , skip this loop\n\n")
        return

    for corner_value in corner_step_list:
        logging.info(f'corner_value {corner_value}')
        logging.info('set corner value')
        value = corner_value[0] if isinstance(corner_value, tuple) else corner_value
        corner_tool.execute_turntable_cmd('rt', angle=value)
        logging.info(corner_tool.get_turntanle_current_angle())

        with open(pytest.testResult.detail_file, 'a') as f:
            f.write('-' * 40 + '\n')
            info, corner_set = '', ''
            db_set = 0
            info += 'db_set :  \n'
            corner_set = corner_value[0] if isinstance(corner_value, tuple) else corner_value
            info += 'corner_set : ' + str(corner_set) + '\n'
            f.write(info)

        rssi_num = pytest.dut.get_rssi()
        logging.info('start test tx/rx')
        logging.info(f'router_info: {router_info}')
        if int(router_info.test_type):
            logging.info(f'rssi : {rssi_num} ')
            pytest.dut.get_tx_rate(router_info, 'TCP',
                                   corner_tool=corner_tool,
                                   db_set=db_set)
        if int(router_info.test_type):
            logging.info(f'rssi : {rssi_num}')
            pytest.dut.get_rx_rate(router_info, 'TCP',
                                   corner_tool=corner_tool,
                                   db_set=db_set)
