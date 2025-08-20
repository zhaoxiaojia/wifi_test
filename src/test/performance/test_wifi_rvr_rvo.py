# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
File       : test_wifi_rvr_rvo.py
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

from src.test.performance import common_setup, init_rf, init_corner

cfg = load_config(refresh=True)
router_name = cfg['router']['name']
router = get_router(router_name)
logging.info(f'router {router}')
test_data = get_testdata(router)
rf_step_list = [i for i in range(*cfg['rf_solution']['step'])][::3]
corner_step_list = [i for i in range(*cfg['corner_angle']['step'])][::45]


def pre_setup(cfg, _router):
    rf_tool, _ = init_rf(cfg)
    corner_tool, _ = init_corner(cfg)
    return rf_tool, corner_tool


@pytest.fixture(scope='session', params=test_data, ids=[str(i) for i in test_data])
def setup_router(request):
    router_info = request.param
    cfg = load_config(refresh=True)
    router = get_router(cfg['router']['name'])
    pre = getattr(request.module, 'pre_setup', None)
    extra = pre(cfg, router) if callable(pre) else None
    connect_status = common_setup(cfg, router, router_info)
    step_list = (corner_step_list, rf_step_list)
    try:
        yield connect_status, router_info, step_list, extra
    finally:
        pytest.dut.kill_iperf()
        if extra:
            rf_tool, _ = extra
            logging.info('Reset rf value')
            rf_tool.execute_rf_cmd(0)
            logging.info(rf_tool.get_rf_current_value())
            time.sleep(10)


@pytest.fixture(scope="function", params=corner_step_list)
def setup_corner(request, setup_router):
    corner_set = request.param[0] if isinstance(request.param, tuple) else request.param
    rf_step_list = setup_router[2][1]
    rf_tool, corner_tool = setup_router[3]
    corner_tool.execute_turntable_cmd("rt", angle=corner_set)
    yield (
        setup_router[0],
        setup_router[1],
        corner_set,
        corner_tool,
        rf_step_list,
        rf_tool,
    )


@pytest.fixture(scope="function", params=rf_step_list)
def setup_rf(request, setup_corner):
    db_set = request.param[1] if isinstance(request.param, tuple) else request.param
    connect_status, router_info, corner_set, corner_tool, _, rf_tool = setup_corner
    rf_tool.execute_rf_cmd(db_set)
    yield connect_status, router_info, corner_set, db_set, rf_tool, corner_tool


def test_rvr_rvo(setup_rf):
    connect_status, router_info, corner_set, db_set, rf_tool, corner_tool = setup_rf
    if not connect_status:
        logging.info("Can't connect wifi ,input 0")
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write("\n Can't connect wifi , skip this loop\n\n")
        return

    with open(pytest.testResult.detail_file, 'a') as f:
        f.write('-' * 40 + '\n')
        info = ''
        info += 'db_set : ' + str(db_set) + '\n'
        info += 'corner_set : ' + str(corner_set) + '\n'
        f.write(info)

    pytest.dut.get_rssi()
    logging.info('start test iperf')
    logging.info(f'router_info: {router_info}')
    if int(router_info.tx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_tx_rate(router_info, 'TCP', corner_tool=corner_tool, db_set=db_set)
    if int(router_info.rx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_rx_rate(router_info, 'TCP', corner_tool=corner_tool, db_set=db_set)
