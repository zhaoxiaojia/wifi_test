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

from src.tools.config_loader import load_config

from src.test.performance import common_setup, init_corner, init_router

cfg = load_config(refresh=True)
test_data = get_testdata(init_router(cfg))
corner_step_list = [i for i in range(*cfg['corner_angle']['step'])][::45]


def pre_setup(cfg, _router):
    corner_tool, _ = init_corner(cfg)
    return corner_tool


@pytest.fixture(scope='session', params=test_data, ids=[str(i) for i in test_data])
def setup_router(request):
    router_info = request.param
    cfg = load_config(refresh=True)
    router = init_router(cfg)
    pre = getattr(request.module, 'pre_setup', None)
    extra = pre(cfg, router) if callable(pre) else None
    connect_status = common_setup(cfg, router, router_info)
    step_list = corner_step_list
    try:
        yield connect_status, router_info, step_list, extra
    finally:
        pytest.dut.kill_iperf()


@pytest.fixture(scope="function", params=corner_step_list)
def setup_corner(request, setup_router):
    value = request.param[0] if isinstance(request.param, tuple) else request.param
    corner_tool = setup_router[3]
    corner_tool.execute_turntable_cmd("rt", angle=value)
    yield setup_router[0], setup_router[1], value, corner_tool


def test_rvo(setup_corner):
    connect_status, router_info, corner_set, corner_tool = setup_corner
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write("\n Can't connect wifi , skip this loop\n\n")
        return

    with open(pytest.testResult.detail_file, 'a') as f:
        f.write('-' * 40 + '\n')
        info, db_set = '', 0
        info += 'db_set :  \n'
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
