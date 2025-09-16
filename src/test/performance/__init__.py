#!/usr/bin/env python
# encoding: utf-8
"""
通用性能测试工具
"""
import logging
import re
import time
from typing import Any
from functools import lru_cache

import pytest

from src.tools.config_loader import load_config
from src.tools.router_tool.Router import Router
from src.tools.router_tool.router_factory import get_router
from src.tools.connect_tool.lab_device_controller import LabDeviceController
from src.tools.rs_test import rs
@lru_cache(maxsize=1)
def get_cfg() -> Any:
    """返回最新的配置"""
    return load_config(refresh=True)


def init_rf():
    """根据配置初始化射频衰减器"""
    cfg = get_cfg()
    rf_solution = cfg['rf_solution']
    model = rf_solution['model']
    if model not in ['RADIORACK-4-220', 'RC4DAT-8G-95', 'RS232Board5']:
        raise EnvironmentError("Doesn't support this model")
    if model == 'RS232Board5':
        rf_tool = rs()
    else:
        rf_ip = rf_solution[model]['ip_address']
        rf_tool = LabDeviceController(rf_ip)
        logging.info(f'rf_ip {rf_ip}')
    logging.info('Reset rf value')
    rf_tool.execute_rf_cmd(0)
    time.sleep(3)
    return rf_tool


def init_corner():
    """根据配置初始化转台"""
    cfg = get_cfg()
    corner_ip = cfg['corner_angle']['ip_address']
    corner_tool = rs() if corner_ip == '192.168.5.11' else LabDeviceController(corner_ip)
    logging.info(f'corner_ip {corner_ip}')
    logging.info('Reset corner')
    corner_tool.set_turntable_zero()
    logging.info(corner_tool.get_turntanle_current_angle())
    time.sleep(3)
    return corner_tool


def init_router() -> Router:
    """根据配置返回路由实例"""
    cfg = get_cfg()
    router = get_router(cfg['router']['name'])
    logging.info(f'router {router}')
    return router


def common_setup(router: Router, router_info: Router) -> bool:
    """通用的性能测试前置步骤"""
    logging.info("router setup start")

    pytest.dut.skip_tx = False
    pytest.dut.skip_rx = False

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

    logging.info(f'dut try to connect {router_info.ssid}')
    if pytest.connect_type == 'telnet':
        connect_status = True
        time.sleep(90)
    else:
        connect_status = False
        for _ in range(3):
            try:
                wpa_type = 'wpa3' if 'WPA3' in router_info.security_mode else 'wpa2'
                if router_info.security_mode.lower() in [
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
                    cmd=cmd,
                    target=re.findall(r'(\d+\.\d+\.\d+\.)', pytest.dut.pc_ip)[0],
                ):
                    connect_status = True
                    break
            except Exception as e:
                logging.info(e)
                connect_status = False

    logging.info(f'dut_ip:{pytest.dut.dut_ip}')
    logging.info(f'pc_ip:{pytest.dut.pc_ip}')
    logging.info('dut connected')

    cfg = load_config(refresh=True)
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

    return connect_status


@lru_cache(maxsize=1)
def get_rf_step_list():
    cfg = get_cfg()
    rf_solution = cfg['rf_solution']
    return [i for i in range(*rf_solution['step'])][::6]


@lru_cache(maxsize=1)
def get_corner_step_list():
    cfg = get_cfg()
    corner_step = cfg['corner_angle']['step']
    return [i for i in range(*corner_step)][::45]
