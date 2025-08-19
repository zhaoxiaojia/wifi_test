#!/usr/bin/env python
# encoding: utf-8
"""
通用性能测试工具
"""
import logging
import re
import time
from typing import Callable, Generator, Tuple

import pytest

from src.tools.config_loader import load_config
from src.tools.router_tool.Router import Router
from src.tools.router_tool.router_factory import get_router
from src.tools.connect_tool.lab_device_controller import LabDeviceController
from src.tools.rs_test import rs


def init_rf(cfg: dict):
    """根据配置初始化射频衰减器"""
    rf_solution = cfg['rf_solution']
    model = rf_solution['model']
    if model not in ['RADIORACK-4-220', 'RC4DAT-8G-95', 'XIN-YI']:
        raise EnvironmentError("Doesn't support this model")
    if model == 'XIN-YI':
        rf_tool = rs()
    else:
        rf_ip = rf_solution[model]['ip_address']
        rf_tool = LabDeviceController(rf_ip)
        logging.info(f'rf_ip {rf_ip}')
    rf_step_list = [i for i in range(*rf_solution['step'])][::3]
    logging.info('Reset rf value')
    rf_tool.execute_rf_cmd(0)
    logging.info(rf_tool.get_rf_current_value())
    time.sleep(30)
    return rf_tool, rf_step_list


def init_corner(cfg: dict):
    """根据配置初始化转台"""
    corner_ip = cfg['corner_angle']['ip_address']
    corner_tool = rs() if corner_ip == '192.168.5.11' else LabDeviceController(corner_ip)
    logging.info(f'corner_ip {corner_ip}')
    corner_step = cfg['corner_angle']['step']
    corner_step_list = [i for i in range(*corner_step)][::45]
    logging.info('Reset corner')
    corner_tool.set_turntable_zero()
    logging.info(corner_tool.get_turntanle_current_angle())
    time.sleep(3)
    return corner_tool, corner_step_list


def common_setup(request, pre_setup: Callable | None = None) -> Generator[
    Tuple[bool, Router, Router, dict], None, None
]:
    """通用的性能测试前置步骤

    Parameters
    ----------
    request: pytest.FixtureRequest
        pytest 传入的 request 对象
    pre_setup: Callable | None
        在路由器配置和连接之前执行的额外初始化函数，
        接收 (cfg, router) 两个参数。

    Yields
    ------
    Tuple[bool, Router, Router, dict]
        (connect_status, router_info, router, cfg)
    """
    logging.info("router setup start")
    cfg = load_config(refresh=True)
    router_name = cfg['router']['name']
    router = get_router(router_name)

    pytest.dut.skip_tx = False
    pytest.dut.skip_rx = False

    if pre_setup:
        pre_setup(cfg, router)

    router_info = request.param
    router.change_setting(router_info), "Can't set ap , pls check first"
    if pytest.connect_type == 'telnet':
        if router_info.band == "2.4G":
            router.change_country("欧洲")
        else:
            router.change_country("美国")
        router.driver.quit()
        band = '5G' if '2' in router_info.band else '2.4G'
        ssid = router_info.ssid + "_bat"
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
        connect_status = False
        for _ in range(3):
            try:
                wpa_type = 'wpa3' if 'WPA3' in router_info.security_protocol else 'wpa2'
                if router_info.security_protocol.lower() in [
                    'open', '不加密', '无', 'open system', '无加密(允许所有人连接)', 'none'
                ]:
                    logging.info('no passwd')
                    cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, "open", "")
                else:
                    cmd = pytest.dut.CMD_WIFI_CONNECT.format(
                        router_info.ssid, wpa_type, router_info.password
                    )
                if router_info.hide_ssid == '是':
                    cmd += pytest.dut.CMD_WIFI_HIDE
                pytest.dut.checkoutput(cmd)
                time.sleep(5)
                if pytest.dut.wait_for_wifi_address(
                    target=re.findall(r'(\d+\.\d+\.\d+\.)', pytest.dut.pc_ip)[0]
                ):
                    connect_status = True
                    break
            except Exception as e:
                logging.info(e)
                connect_status = False

    logging.info(f'dut_ip:{pytest.dut.dut_ip}')
    logging.info(f'pc_ip:{pytest.dut.pc_ip}')
    logging.info('dut connected')

    rvr_tool = cfg['rvr']['tool']
    if rvr_tool == 'ixchariot':
        script = (
            'set script "$ixchariot_installation_dir/Scripts/High_Performance_Throughput.scr"\n'
            if '5' in router_info.band
            else 'set script "$ixchariot_installation_dir/Scripts/Throughput.scr"\n'
        )
        pytest.dut.ix.modify_tcl_script("set script ", script)
        pytest.dut.checkoutput(pytest.dut.IX_ENDPOINT_COMMAND)
        time.sleep(3)

    yield connect_status, router_info, router, cfg

    if pytest.connect_type == 'telnet':
        router.change_country("欧洲")
        router.driver.quit()
    pytest.dut.kill_iperf()
