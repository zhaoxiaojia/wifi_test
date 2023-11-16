# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_rvr.py
# Time       ：2023/9/15 14:03
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import csv
import logging
import os
import random
import re
import signal
import subprocess
import tempfile
import threading
import time

import _io
import pytest
import bisect

from Router import Router
from tools.TelnetInterface import TelnetInterface
# from tools.UsbControl import UsbControl
from tools.yamlTool import yamlTool
from Decorators import set_timeout
from tools.Asusax86uControl import Asusax86uControl
from tools.Asusax88uControl import Asusax88uControl
import itertools

# 读取 测试配置
with open(os.getcwd() + '/config/asusax88u.csv', 'r') as f:
    reader = csv.reader(f)
    test_data = [Router(*[i.strip() for i in row]) for row in reader][1:]
logging.info(test_data)

# 设置为True 时跳过 衰减 相关操作
rf_debug = False
# 设置为True 时跳过 转台 相关操作
corner_debug = True
# 设置为True 时跳过 路由 相关操作
router_debug = False
# 设置DUT iperf 运行命令 iperf 或者 iperf3
dut_iperf = 'iperf3'
# 设置pc iperf 运行命令 iperf 或者 iperf3
pc_ipef = 'iperf3'

# 设置是否需要push iperf
push_iperf = True
# 无法使用 命令行 连接wifi 是 设置为true
third_dut = False
if pytest.connect_type == 'telnet':
    third_dut = True

sum_list_lock = threading.Lock()

# loading config_wifi.yaml 文件 获取数据  dict 数据类型
wifi_yaml = yamlTool(os.getcwd() + '/config/config_wifi.yaml')
command_data = wifi_yaml.get_note('env_command')
router_name = wifi_yaml.get_note('router')['name']
router = ''

# 实例路由器对象
if not router_debug:
    exec(f'router = {router_name.capitalize()}Control()')

env_control = wifi_yaml.get_note('env_control')

# 定义测试类型 衰减 或 转台 或共存
test_type = ''
if 'rf' in env_control:
    test_type = 'rf'
if 'corner' in env_control:
    test_type = 'corner'
if 'rf' in env_control and 'corner' in env_control:
    test_type = 'both'

if test_type == '':
    raise ValueError("test_type error")

# 初始化 衰减 & 转台 对象
if test_type == 'rf' or test_type == 'both':
    # 读取衰减 配置
    rf_step_list = []
    model = wifi_yaml.get_note('rf_solution')['model']
    if model != 'RADIORACK-4-220' and model != 'RC4DAT-8G-95':
        raise EnvironmentError("Doesn't support this model")

    if model == 'RADIORACK-4-220':
        rf_ip = wifi_yaml.get_note('rf_solution')[model]['ip_address']
    if model == 'RC4DAT-8G-95':
        rf_ip = '192.168.50.19'

    if not rf_debug:
        logging.info('test rf')
        rf_tool = TelnetInterface(rf_ip)
        logging.info(f'rf_ip {rf_ip}')
        rf_step_list = wifi_yaml.get_note('rf_solution')['step']
        rf_step_list = [i for i in range(*rf_step_list)][::2]
        logging.info(f'rf_step_list {rf_step_list}')

if test_type == 'corner' or test_type == 'both':
    corner_step_list = []
    # 配置衰减
    corner_ip = wifi_yaml.get_note('corner_angle')['ip_address']
    if not corner_debug:
        logging.info('test corner')
        corner_tool = TelnetInterface(corner_ip)
        logging.info(f'corner_ip {corner_ip}')
        corner_step_list = wifi_yaml.get_note('corner_angle')['step']
        corner_step_list = [i for i in range(*corner_step_list)][::45]
        logging.info(f'corner step_list {corner_step_list}')

# step_list_rf = wifi_yaml.get_note('rf_solution')['step']
# rf_step_list = [i for i in range(*step_list_rf)][::]
#
# step_list_corner = wifi_yaml.get_note('corner_angle')['step']
# corner_step_list = [i for i in range(*step_list_corner)][::45]
step_list = [1]
if test_type == 'rf' and rf_step_list:
    step_list = rf_step_list
if test_type == 'corner' and corner_step_list:
    step_list = corner_step_list
if test_type == 'both' and rf_step_list and corner_step_list:
    step_list = itertools.product(corner_step_list, rf_step_list)

# 配置 测试报告
pytest.testResult.x_path = [] if test_type == 'both' else step_list
pytest.testResult.init_rvr_result()
tx_result_list, rx_result_list = [], []
rx_result, tx_result = '', ''


def iperf_on(command, adb):
    def server_on():
        logging.info(f'server {command} ->{adb}<-')
        with open('temp.txt', 'w') as f:
            if adb == 'executer':
                iperf_log = pytest.executer.checkoutput(command)
                f.write(iperf_log)
            popen = subprocess.Popen(command.split(), stdout=f, encoding='gbk')
        logging.info(subprocess.run('tasklist | findstr "iperf"'.replace('iperf',pc_ipef),shell=True,encoding='gbk'))
        # logging.info(pytest.executer.checkoutput('ps -A|grep "iperf"'.replace('iperf',dut_iperf)))
        logging.info('write done')
        return popen

    # if adb == 'executer':
    #     # 使用telnet 时 dut 场景
    #     logging.info('telnet dut ')
    #     command = command.replace('iperf', dut_iperf)
    #     if dut_iperf == 'iperf3':
    #         command = command.replace('-w 4m', '')
    #     logging.info(f'telnet adb {command}')
    #     pytest.executer.checkoutput(command)
    #     if re.findall(r'iperf[3]?.*?-s', command):
    #         popen = server_on()
    #     return popen
    if adb:
        command = command.replace('iperf', dut_iperf)
        if dut_iperf == 'iperf3':
            command = command.replace('-w 4m', '')
        if adb != 'executer':
            command = f'adb -s {adb} shell ' + command
    else:
        command = command.replace('iperf', pc_ipef)
        if pc_ipef == 'iperf3':
            command = command.replace('-w 4m', '')
    logging.info(f'command {command} ->{adb}<-')

    if re.findall(r'iperf[3]?.*?-s', command):
        popen = server_on()
    else:
        if adb == 'executer':
            pytest.executer.checkoutput(command)
        popen = subprocess.Popen(command.split(), encoding='gbk')
    return popen


def server_off(popen):
    if pytest.connect_type == 'adb':
        if not isinstance(popen, subprocess.Popen):
            logging.warning('pls pass in the popen object')
            return 'pls pass in the popen object'
        try:
            os.kill(popen.pid, signal.SIGTERM)
        except Exception as e:
            ...
        popen.terminate()
    elif pytest.connect_type == 'telnet':
        pytest.executer.tn.close()


def get_logcat(pair):
    # pytest.executer.kill_iperf()
    # 分析 iperf 测试结果
    result_list = []
    with open('temp.txt', 'r') as f:
        for line in f.readlines():
            logging.info(f'line : {line.strip()}')
            if pair != 1:
                if '[SUM]' not in line:
                    continue
            if re.findall(r'.*?\d+\.\d*-\s*\d+\.\d*.*?(\d+\.*\d*)\s+Mbits/sec.*?', line.strip(), re.S):
                result_list.append(
                    int(float(re.findall(r'.*?\d+\.\d*-\s*\d+\.\d*.*?(\d+\.*\d*)\s+Mbits/sec.*?', line.strip(), re.S)[0])))

    if result_list:
        logging.info(f'{sum(result_list) / len(result_list)}')
        logging.info(f'{result_list}')
        result = sum(result_list) / len(result_list)
    else:
        result = 0
    return result


@pytest.fixture(scope='session', autouse=True, params=test_data)
def wifi_setup_teardown(request):
    global tx_result_list, rx_result_list, rx_result, tx_result
    logging.info('==== wifi env setup start')

    router_info = request.param
    if not router_debug:
        # 修改路由器配置
        assert router.change_setting(router_info), "Can't set ap , pls check first"

    logging.info('wifi env set done')
    with open(pytest.testResult.detail_file, 'a', encoding='gbk') as f:
        f.write(f'Testing {router_info} \n')

    # 重置衰减&转台
    if 'rf' in env_control:
        # 衰减器置0
        if not rf_debug:
            logging.info('Reset rf value')
            rf_tool.execute_rf_cmd(0)
            logging.info(rf_tool.get_rf_current_value())
            time.sleep(10)
    if 'corner' in env_control:
        # 转台置0
        if not rf_debug:
            logging.info('Reset corner')
            corner_tool.set_turntable_zero()
            logging.info(corner_tool.get_turntanle_current_angle())
            time.sleep(3)

    if third_dut:
        connect_status = True
        if not router_debug:
            # router 有修改时 等待 30 秒 让板子回连
            time.sleep(30)
    else:
        # 连接 网络 最多三次重试
        for _ in range(3):
            try:
                if int(pytest.executer.getprop('ro.build.version.sdk')) >= 30 and not router_info.wep_encrypt:
                    logging.info('sdk over 30 ')
                    type = 'wpa3' if 'WPA3' in router_info.authentication_method else 'wpa2'
                    if router_info.authentication_method.lower() in \
                            ['open', '不加密', '无', 'open system', '无加密(允许所有人连接)', 'none']:
                        logging.info('no passwd')
                        cmd = pytest.executer.CMD_WIFI_CONNECT_OPEN.format(router_info.ssid)
                    else:
                        cmd = pytest.executer.CMD_WIFI_CONNECT.format(router_info.ssid, type,
                                                                      router_info.wpa_passwd)
                    if router_info.hide_ssid == '是':
                        if int(pytest.executer.getprop('ro.build.version.sdk')) >= 31:
                            cmd += pytest.executer.CMD_WIFI_HIDE
                        else:
                            cmd = (pytest.executer.WIFI_CONNECT_COMMAND_REGU.format(router_info.ssid) +
                                   pytest.executer.WIFI_CONNECT_PASSWD_REGU.format(router_info.wpa_passwd) +
                                   pytest.executer.WIFI_CONNECT_HIDE_SSID_REGU.format(router_info.hide_type))
                else:
                    logging.info('sdk less then 30')
                    if router_info.hide_ssid == '是':
                        cmd = (pytest.executer.WIFI_CONNECT_COMMAND_REGU.format(router_info.ssid) +
                               pytest.executer.WIFI_CONNECT_PASSWD_REGU.format(router_info.wpa_passwd) +
                               pytest.executer.WIFI_CONNECT_HIDE_SSID_REGU.format(router_info.hide_type))
                    else:
                        cmd = (pytest.executer.WIFI_CONNECT_COMMAND_REGU.format(router_info.ssid) +
                               pytest.executer.WIFI_CONNECT_PASSWD_REGU.format(router_info.wpa_passwd))
                pytest.executer.checkoutput(cmd)
                if pytest.executer.wait_for_wifi_address():
                    connect_status = True
                    break
            except Exception as e:
                logging.info(e)
                connect_status = False

    if pytest.connect_type == 'telnet':
        pytest.executer.dut_ip = pytest.executer.ip
    elif not router_debug:
        dut_info = pytest.executer.checkoutput('ifconfig wlan0')
        pytest.executer.dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)[0]
    else:
        pytest.executer.dut_ip = ''
    logging.info(f'dut_ip:{pytest.executer.dut_ip}')
    logging.info('==== wifi env setup done')
    connect_status = True
    yield connect_status, router_info
    # 后置动作
    # 重置结果
    tx_result_list, rx_result_list = [], []
    if not router_debug:
        router.router_control.driver.quit()


@pytest.fixture(scope='session', autouse=True, params=command_data)
def session_setup_teardown(request):
    logging.info('==== debug command setup start')
    # iperf 配置
    if push_iperf and pytest.connect_type == 'adb' and (
            pytest.executer.checkoutput('[ -e /system.bin/iperf ] && echo yes || echo no').strip() != 'yes'):
        path = os.path.join(os.getcwd(), 'res/iperf')
        pytest.executer.push(path, '/system/bin')
        pytest.executer.checkoutput('chmod a+x /system/bin/iperf')

    # 获取板子的ip 地址
    ipfoncig_info = pytest.executer.checkoutput_term('ipconfig').strip()
    pytest.executer.pc_ip = re.findall(r'IPv4 地址.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
    logging.info(f'pc_ip:{pytest.executer.pc_ip}')
    command_info = request.param
    logging.info(f"command_info : {command_info}")
    pytest.executer.subprocess_run(command_info)
    logging.info('==== debug command setup done')
    yield
    # 后置动作

    # 生成 pdf
    # if step_list != [0]:
    #     pytest.testResult.write_to_excel()
    #     if test_type == 'rf':
    #         # 重置衰减
    #         if not rf_debug:
    #             rf_tool.execute_rf_cmd(0)
    #         # 生成折线图
    #         pytest.testResult.write_attenuation_data_to_pdf()
    #     elif test_type == 'corner':
    #         # 转台重置
    #         if not rf_debug:
    #             corner_tool.set_turntable_zero()
    #         # 生成雷达图
    #         pytest.testResult.write_corner_data_to_pdf()
    #     else:
    #         ...


pair_count = {
    'n': {
        '2': wifi_yaml.get_note('pair_num')['n']['2'],
        '5': wifi_yaml.get_note('pair_num')['n']['5']
    },
    'ac': {
        '5': wifi_yaml.get_note('pair_num')['ac']['5']
    },
    'ax': {
        '2': wifi_yaml.get_note('pair_num')['ax']['2'],
        '5': wifi_yaml.get_note('pair_num')['ax']['5'],
    },
    'auto': {
        '2': wifi_yaml.get_note('pair_num')['auto']['2'],
        '5': wifi_yaml.get_note('pair_num')['auto']['5'],
    }
}


def set_pair_count(router_info, rssi_num, type, dire):
    '''
    匹配 打流通道数
    '''
    if 'AX' in router_info.wireless_mode:
        type = 'ax'
    elif 'AC' in router_info.wireless_mode:
        type = 'ac'
    elif '自动' in router_info.wireless_mode:
        type = 'auto'
    else:
        type = 'n'

    if '2' in router_info.band:
        band = '2'
    else:
        band = '5'

    _2g = [10, 20, 30, 40]
    _5g = [10, 20, 30, 40, 50]

    if band == '2':
        target_list = _2g
    else:
        target_list = _5g
    logging.info(f'rf current db {rssi_num}')
    pair = pair_count[type][band][dire][bisect.bisect(target_list, rssi_num)]
    logging.info(f'pair {pair}')
    return int(pair)


def get_tx_rate(router_info, pair, freq_num, rssi_num, type, corner_set='', db_set=''):
    if not rf_debug or not router_debug:
        # 最多三次 重试机会
        for _ in range(3):
            logging.info('run tx ')
            tx_result = 0
            mcs_tx = 0
            # pytest.executer.checkoutput(pytest.executer.CLEAR_DMESG_COMMAND)
            # pytest.executer.checkoutput(pytest.executer.MCS_TX_KEEP_GET_COMMAND)
            # kill iperf
            pytest.executer.kill_iperf()
            time.sleep(1)
            server = iperf_on(pytest.executer.IPERF_SERVER[type], '')
            iperf_on(pytest.executer.IPERF_CLIENT_REGU[type]['tx'].format(
                pytest.executer.pc_ip,
                pytest.executer.IPERF_TEST_TIME,
                pair if type == 'TCP' else 1), pytest.executer.serialnumber)
            time.sleep(pytest.executer.IPERF_WAIT_TIME)
            if pytest.connect_type == 'telnet':
                time.sleep(15)
            tx_result = get_logcat(pair if type == 'TCP' else 1)
            logging.info(f'get result done : {tx_result}')
            if tx_result == False:
                logging.info("Connect failed")
                continue
            time.sleep(3)
            server_off(server)
            logging.info(f'tx_result {tx_result}')
            mcs_tx = pytest.executer.get_mcs_tx()
            if tx_result and mcs_tx:
                logging.info(f'{tx_result}, {mcs_tx}')
                break
    else:
        tx_result = 70 + random.randrange(200, 300)
        mcs_tx = 'msc_tx'
    corner = 'None'

    if 'corner' in env_control:
        if not rf_debug:
            corner = corner_tool.get_turntanle_current_angle()
        else:
            corner = corner_set

    tx_result_info = (
        f'P0 RvR Standalone NULL Null {router_info.wireless_mode.split()[0]} {router_info.band.split()[0]} '
        f'{router_info.bandwidth.split()[0]} Rate_Adaptation {router_info.channel} {type} UL NULL NULL {db_set} {rssi_num} {corner} NULL {tx_result} {mcs_tx if mcs_tx else "NULL"}')
    logging.info(tx_result_info)
    pytest.testResult.save_result(tx_result_info.replace(' ', ','))
    with open(pytest.testResult.detail_file, 'a') as f:
        f.write(f'Tx {type} result : {tx_result}\n')
        f.write('-' * 40 + '\n\n')


def get_rx_rate(router_info, pair, freq_num, rssi_num, type, corner_set='', db_set=''):
    if not rf_debug or not router_debug:
        for _ in range(3):
            logging.info('run rx ')
            rx_result = 0
            mcs_rx = 0
            # clear mcs data
            # pytest.executer.checkoutput(pytest.executer.CLEAR_DMESG_COMMAND)
            # pytest.executer.checkoutput(pytest.executer.MCS_RX_CLEAR_COMMAND)
            # kill iperf
            pytest.executer.kill_iperf()
            time.sleep(1)
            server = iperf_on(pytest.executer.IPERF_SERVER[type], pytest.executer.serialnumber)
            iperf_on(
                pytest.executer.IPERF_CLIENT_REGU[type]['rx'].format(
                    pytest.executer.dut_ip, pytest.executer.IPERF_TEST_TIME,
                    pair if type == 'TCP' else 4), '')
            time.sleep(pytest.executer.IPERF_WAIT_TIME)
            if pytest.connect_type == 'telnet':
                time.sleep(15)
            rx_result = get_logcat(pair if type == 'TCP' else 4)
            if rx_result == False:
                logging.info("Connect failed")
                continue
            time.sleep(3)
            server_off(server)
            # get mcs data
            mcs_rx = pytest.executer.get_mcs_rx()
            if rx_result and mcs_rx:
                logging.info(f'{rx_result}, {mcs_rx}')
                break
    else:
        rx_result = 70 + random.randrange(200, 300)
        mcs_rx = 'mcs_rx'
    corner = 'None'
    if 'corner' in env_control:
        if not rf_debug:
            corner = corner_tool.get_turntanle_current_angle()
        else:
            corner = corner_set

    rx_result_info = (
        f'P0 RvR Standalone NULL Null {router_info.wireless_mode.split()[0]} {router_info.band.split()[0]} '
        f'{router_info.bandwidth.split()[0]} Rate_Adaptation {router_info.channel} {type} DL NULL NULL {db_set} {rssi_num} {corner} NULL {rx_result} {mcs_rx if mcs_rx else "NULL"}')
    pytest.testResult.save_result(rx_result_info.replace(' ', ','))
    with open(pytest.testResult.detail_file, 'a', encoding='gbk') as f:
        logging.info('writing')
        f.write(f'Rx {type} result : {rx_result}\n')
        f.write('-' * 40 + '\n\n')


# 测试 iperf
@pytest.mark.parametrize("rf_value", step_list)
def test_wifi_rvr(wifi_setup_teardown, rf_value):
    global rx_result, tx_result, rx_result_list, tx_result_list
    # 判断板子是否存在  ip
    if not wifi_setup_teardown[0]:
        logging.info("Can't connect wifi ,input 0")
        rx_result_list.append('0')
        tx_result_list.append('0')
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write("\n Can't connect wifi , skip this loop\n\n")
        return
    router_info = wifi_setup_teardown[1]

    # 执行 修改 步长
    if test_type == 'rf' or test_type == 'both':
        # 修改衰减
        if not rf_debug:
            logging.info('set rf value')
            value = rf_value[1] if type(rf_value) == tuple else rf_value
            logging.info(value)
            rf_tool.execute_rf_cmd(value)
            # 获取当前衰减值
            logging.info(rf_tool.get_rf_current_value())
    elif test_type == 'corner' or test_type == 'both':
        if not corner_debug:
            logging.info('set corner value')
            value = rf_value[0] if type(rf_value) == tuple else rf_value
            logging.info(value)
            corner_tool.execute_turntable_cmd('rt', angle=value * 10)
            # 获取转台角度
            logging.info(corner_tool.get_turntanle_current_angle())
    else:
        raise Exception("Doesn't support this type")

    with open(pytest.testResult.detail_file, 'a') as f:
        f.write('-' * 40 + '\n')
        info, corner_set = '', ''
        db_set = 0
        if 'rf' in env_control:
            db_set = rf_value[1] if type(rf_value) == tuple else rf_value
            info += 'db_set : ' + str(db_set) + '\n'

        if 'corner' in env_control:
            corner_set = rf_value[0] if type(rf_value) == tuple else rf_value
            info += 'corner_set : ' + str(corner_set) + '\n'

        f.write(info)
    # time.sleep(1)

    # 获取rssi
    for i in range(3):
        rssi_info = pytest.executer.checkoutput(pytest.executer.IW_LINNK_COMMAND)
        time.sleep(1)
        if 'signal' in rssi_info:
            break
    logging.info(rssi_info)
    if 'Not connected' in rssi_info:
        logging.info('The signal strength is not enough ,input 0')
        rx_result, tx_result, rssi_num = 0, 0, 0
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write('signal strength is not enough no rssi \n')
        assert False, "Wifi is not connected"
    logging.info('Start test')
    try:
        rssi_num = int(re.findall(r'signal:\s+-?(\d+)\s+dBm', rssi_info, re.S)[0])
        freq_num = int(re.findall(r'freq:\s+(\d+)\s+', rssi_info, re.S)[0])
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write(f'Rssi : {rssi_num}\n')
            f.write(f'Freq : {freq_num}\n')
    except IndexError as e:
        rssi_num = -1
        freq_num = -1
    # handle iperf pair count
    logging.info(router_info)
    protocol = 'TCP' if 'TCP' in router_info.protocol_type else 'UDP'
    logging.info(router_info.test_type)
    # iperf  打流
    if 'tx' in router_info.test_type:
        # 动态匹配 打流通道数
        pair = set_pair_count(router_info, db_set, protocol, 'tx')
        logging.info(f'rssi : {rssi_num} pair : {pair}')
        get_tx_rate(router_info, pair, freq_num, rssi_num, protocol, corner_set=corner_set, db_set=db_set)
    if 'rx' in router_info.test_type:
        pair = set_pair_count(router_info, db_set, protocol, 'rx')
        logging.info(f'rssi : {rssi_num} pair : {pair}')
        get_rx_rate(router_info, pair, freq_num, rssi_num, protocol, corner_set=corner_set, db_set=db_set)
