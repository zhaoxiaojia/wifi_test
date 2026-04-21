#!/usr/bin/env python
# -*-coding:utf-8 -*-

"""
File       : test_wifi_rvr.py
Time       : 2023/9/15 14:03
Author     : chao.li
version    : python 3.9
Description:
"""

import logging

import pytest

from src.test import get_testdata
from src.test.pyqt_log import log_fixture_params
from src.test.performance import common_setup, ensure_performance_result, get_cfg, get_rf_step_list, init_rf, init_router, scenario_group, wait_connect
from src.tools.router_tool.Router import router_str

_test_data = get_testdata(init_router())
rf_tool = init_rf()

def pytest_generate_tests(metafunc):
    """
    Pytest hook to dynamically parametrize the 'db_set' fixture.
    """
    if "db_set" in metafunc.fixturenames:
        if hasattr(metafunc, 'module') and hasattr(metafunc.module, '_test_data'):
            first_router_info = metafunc.module._test_data[0]
            current_band = getattr(first_router_info, 'band', '2.4G')
        else:
            current_band = '2.4G'  # fallback

        rf_steps = get_rf_step_list(band=current_band)
        #metafunc.parametrize("db_set", rf_steps)
        metafunc.parametrize("db_set", rf_steps, ids=[str(x) for x in rf_steps])

@pytest.fixture(scope="session", params=_test_data, ids=[router_str(i) for i in _test_data])
@log_fixture_params()
def setup_router(request):
    rf_tool.execute_rf_cmd(0)
    router_info = request.param
    current_band = getattr(router_info, 'band', '2.4G')
    pytest.current_assumed_band = current_band  #
    rf_step_list = get_rf_step_list(band=current_band)
    if not rf_step_list:
        rf_step_list = [0]
    logging.info("[DEBUG_RF] Pre-calculated RF steps for band=%s: %s", current_band, rf_step_list)

    router = init_router()
    common_setup(router, router_info)
    connect_status = wait_connect(router_info)
    yield router_info, connect_status, rf_step_list
    pytest.dut.kill_iperf()
    rf_tool.execute_rf_cmd(0)

@pytest.fixture(scope="function")
@log_fixture_params()
def setup_attenuation(request, setup_router, db_set):
    router_info, connect_status, rf_step_list  = setup_router
    #db_set = rf_step_list
    max_retries = 1
    success = False
    for attempt in range(max_retries + 1):  # +1 to include the initial try
        logging.info(f"[RF] Attempt {attempt + 1}/{max_retries + 1} to set attenuation to {db_set} dB")
        rf_tool.execute_rf_cmd(db_set)
        current_value = rf_tool.get_rf_current_value()

        if current_value == db_set or current_value:
            logging.info(f"[RF] Successfully set attenuation to {db_set} dB")
            success = True
            break
        else:
            logging.warning(f"[RF] Failed to set attenuation. Expected: {db_set} dB, Got: {current_value} dB")
            if attempt < max_retries:
                logging.info(f"[RF] Retrying in 1 second...")
                import time
                time.sleep(5)  # Optional: add a short delay between retries

    if not success:
        logging.error(f"[RF] Failed to set attenuation to {db_set} dB after {max_retries + 1} attempts.")

    logging.info(f"[DEBUG_RF] setup_attenuation db_set={db_set} current={current_value}")
    logging.info("Set attenuation: %s dB", current_value)
    pytest.dut.get_rssi()
    #pytest.dut.get_extended_rssi()
    yield connect_status, router_info, db_set
    pytest.dut.kill_iperf()


def test_rvr(setup_attenuation, performance_sync_manager):
    connect_status, router_info, db_set = setup_attenuation
    test_result = ensure_performance_result()

    band = router_info.band
    mode = router_info.wireless_mode
    bandwidth = router_info.bandwidth
    channel = getattr(router_info, 'channel', '1')
    if '2.4G' in band:
        band_name = '2G'
        if '11n' in mode:
            phy_mode = 'HT20' if '20M' in bandwidth else 'HT40'
        else:  # Assume 11ax or others
            phy_mode = 'HE20' if '20M' in bandwidth else 'HE40'
    elif '5G' in band:
        band_name = band
        if '11ac' in mode:
            phy_mode = 'VHT80'
        elif '11ax' in mode:
            phy_mode = 'HE80'
        else:
            # Fallback for unknown modes
            phy_mode = 'HE80'
    else:
        phy_mode = 'UNKNOWN'

    if int(channel) <= 6:
        channel_name = f"{channel}l"
    elif int(channel) <= 13:
        channel_name = f"{channel}u"
    else:
        channel_name = channel


    new_log_message = f"{band_name}_{phy_mode}_CH{channel_name}_RX_Angle:0° Att:{db_set}db"

    with scenario_group(router_info):
        test_result.ensure_log_file_prefix("RVR")
        if not connect_status:
            logging.info("Cannot connect to Wi-Fi, skip remaining steps")
        else:
            logging.info("Start iperf test tx %s rx %s", router_info.tx, router_info.rx)

            if int(router_info.tx):
                tx_log_message = f"{new_log_message.replace('_RX', '_TX')}"
                logging.info("Starting RVR test %s", tx_log_message)
                logging.info("RSSI during TX: %s", pytest.dut.rssi_num)
                pytest.dut.get_tx_rate(router_info, "TCP", db_set=db_set)

                ext_rssi = getattr(pytest.dut, '_extended_rssi_result', None)
                mcs_tx = getattr(pytest.dut, '_mcs_tx_result', "N/A")
                mcs_rx = getattr(pytest.dut, '_mcs_rx_result', "N/A")

                if ext_rssi:
                    bcn, wf0, wf1 = ext_rssi
                    logging.info(f"TX Extended RSSI => bcn: {bcn}, wf0: {wf0}, wf1: {wf1}")

            if int(router_info.rx):
                logging.info("Starting RVR test %s", new_log_message)
                logging.info("RSSI during RX: %s", pytest.dut.rssi_num)
                pytest.dut.get_rx_rate(router_info, "TCP", db_set=db_set)
                ext_rssi = getattr(pytest.dut, '_extended_rssi_result', None)
                mcs_tx = getattr(pytest.dut, '_mcs_tx_result', "N/A")
                mcs_rx = getattr(pytest.dut, '_mcs_rx_result', "N/A")

                if ext_rssi:
                    bcn, wf0, wf1 = ext_rssi
                    logging.info(f"TX Extended RSSI => bcn: {bcn}, wf0: {wf0}, wf1: {wf1}")

    performance_sync_manager(
        "RVR",
        test_result.log_file,
        message="RVR data rows stored in database",
    )
