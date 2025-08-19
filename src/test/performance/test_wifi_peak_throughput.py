# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_wifi_rvr_rvo.py
# Time       ：2023/9/15 14:03
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import re
import threading
import time
from src.test import get_testdata
import pytest

from src.tools.router_tool.router_factory import get_router
from src.tools.config_loader import load_config
from src.tools.router_tool.Router import Router

router_name = load_config(refresh=True)['router']['name']
# 实例路由器对象
router = get_router(router_name)
logging.info(f'router {router}')
test_data = get_testdata(router)

sum_list_lock = threading.Lock()
step_list = [0]



# 配置 测试报告
# pytest.testResult.x_path = [] if (rf_needed and corner_needed) == 'both' else step_list


@pytest.fixture(scope='session', params=test_data, ids=[str(i) for i in test_data])
def setup(request):
    pytest.dut.skip_tx = False
    pytest.dut.skip_rx = False
    logging.info('router setup start')
    cfg = load_config(refresh=True)
    rvr_tool = cfg['rvr']['tool']
    # push_iperf()
    router_info = request.param
    # 修改路由器配置
    assert router.change_setting(router_info), "Can't set ap , pls check first"
    if pytest.connect_type == 'telnet':
        band = '5G' if '2' in router_info.band else '2.4G'
        ssid = router_info.ssid + "_bat";
        router.change_setting(Router(band=band, ssid=ssid))
    time.sleep(3)

    logging.info('router set done')
    with open(pytest.testResult.detail_file, 'a', encoding='utf-8') as f:
        f.write(f'Testing {router_info} \n')

    logging.info(f'dut try to connect {router_info.ssid}')
    if pytest.connect_type == 'telnet':
        connect_status = True
        time.sleep(90)
    else:
        # 连接 网络 最多三次重试
        for _ in range(3):
            try:
                type = 'wpa3' if 'WPA3' in router_info.security_protocol else 'wpa2'
                if router_info.security_protocol.lower() in \
                        ['open', '不加密', '无', 'open system', '无加密(允许所有人连接)', 'none']:
                    logging.info('no passwd')
                    cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, "open", "")
                else:
                    cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, type,
                                                             router_info.password)
                if router_info.hide_ssid == '是':
                    cmd += pytest.dut.CMD_WIFI_HIDE

                pytest.dut.checkoutput(cmd)
                time.sleep(5)

                if pytest.dut.wait_for_wifi_address(target=re.findall(r'(\d+\.\d+\.\d+\.)', dut_ip)[0]):
                    connect_status = True
                    break
            except Exception as e:
                logging.info(e)
                connect_status = False

    logging.info(f'dut_ip:{pytest.dut.dut_ip}')
    connect_status = True

    logging.info(f'pc_ip:{pytest.dut.pc_ip}')
    logging.info('dut connected')

    if rvr_tool == 'ixchariot':
        if '5' in router_info.band:
            pytest.dut.ix.modify_tcl_script("set script ",
                                            'set script "$ixchariot_installation_dir/Scripts/High_Performance_Throughput.scr"\n')
        else:
            pytest.dut.ix.modify_tcl_script("set script ",
                                            'set script "$ixchariot_installation_dir/Scripts/Throughput.scr"\n')
        pytest.dut.checkoutput(pytest.dut.IX_ENDPOINT_COMMAND)
        time.sleep(3)

    yield connect_status, router_info
    # 后置动作
    pytest.dut.kill_iperf()


# 测试 iperf
@pytest.mark.parametrize("rf_value", step_list)
def test_rvr(setup, rf_value):
    # 判断板子是否存在  ip
    if not setup[0]:
        logging.info("Can't connect wifi ,input 0")
        # rx_result_list.append('0')
        # tx_result_list.append('0')
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
    # time.sleep(1)

    pytest.dut.get_rssi()
    # handle iperf pair count
    logging.info('start test tx/rx')
    # iperf  打流
    if int(router_info.tx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_tx_rate(router_info , 'TCP',
                               db_set=db_set)
    if int(router_info.rx):
        logging.info(f'rssi : {pytest.dut.rssi_num}')
        pytest.dut.get_rx_rate(router_info, 'TCP',
                               db_set=db_set)
