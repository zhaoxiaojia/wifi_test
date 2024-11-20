# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_rvr.py
# Time       ：2023/9/15 14:03
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import itertools
import logging
import os
import re
import signal
import subprocess
import threading
import time

import psutil
import pytest

from tools.connect_tool.TelnetInterface import TelnetInterface
from tools.ixchariot import ix
from tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl

from tools.router_tool.Router import Router
from tools.router_tool.Xiaomi.Xiaomiax3000Control import Xiaomiax3000Control
from tools.router_tool.Xiaomi.XiaomiRouterConfig import Xiaomiax3000Config
from test import get_testdata
from tools.yamlTool import yamlTool


# 小米极限测试 记录
# filename = 'XiaoMi-Rvr.xlsx'
# rvr_xlsx = openpyxl.load_workbook(filename)
# sheet = rvr_xlsx['Sheet1']
# new_sheet = rvr_xlsx.create_sheet(title=f'{pytest.timestamp}')

# for row in sheet.iter_rows(values_only=False):
#     for cell in row:
#         new_sheet[cell.coordinate].value = copy(cell.value)
#         new_sheet[cell.coordinate].font = copy(cell.font)
#         new_sheet[cell.coordinate].border = copy(cell.border)
#         new_sheet[cell.coordinate].fill = copy(cell.fill)
#         new_sheet[cell.coordinate].number_format = copy(cell.number_format)
#         new_sheet[cell.coordinate].protection = copy(cell.protection)
#         new_sheet[cell.coordinate].alignment = copy(cell.alignment)
#
# for merged_range in sheet.merged_cells.ranges:
#     new_sheet.merge_cells(str(merged_range))
#
# rvr_xlsx.save(filename)


# def writeInExcelArea(value, row_num, col_num):
#     for i in range(0, len(value)):
# logging.info(f'execl write {row_num} {i + col_num}')
# new_sheet.cell(row=row_num, column=i + col_num, value=value[i])
def modify_tcl_script(old_str, new_str):
    file = './script/rvr.tcl'
    with open(file, "r", encoding="utf-8") as f1, open("%s.bak" % file, "w", encoding="utf-8") as f2:
        for line in f1:
            if old_str in line:
                line = new_str
            f2.write(line)
    os.remove(file)
    os.rename("%s.bak" % file, file)


wifi_yaml = yamlTool(os.getcwd() + '/config/config.yaml')
router_name = wifi_yaml.get_note('router')['name']
test_data = get_testdata()
# 设置为True 时 开启 衰减测试流程
rf_needed = False
# 设置为True 时 开启 状态测试流程
corner_needed = False
# 设置为True 时 开启 路由相关配置
router_needed = True

# 设置是否需要push iperf
iperf_tool = False

if pytest.connect_type == 'telnet':
    third_dut = True

sum_list_lock = threading.Lock()

rvr_tool = wifi_yaml.get_note('rvr')['tool']
if rvr_tool == 'iperf':
    test_tool = wifi_yaml.get_note('rvr')[rvr_tool]['version']
    tool_path = wifi_yaml.get_note('rvr')[rvr_tool]['path'] or ''
    logging.info(f'test_tool {test_tool}')
if rvr_tool == 'ixchariot':
    ix = ix()
    test_tool = wifi_yaml.get_note('rvr')[rvr_tool]
    script_path = test_tool['path']
    logging.info(f'path {script_path}')
    logging.info(f'test_tool {test_tool}')
    modify_tcl_script("set ixchariot_installation_dir ", f"set ixchariot_installation_dir \"{script_path}\"\n")

if __name__ == '__main__':
    # 实例路由器对象
    if router_needed:
        exec(f'router = {router_name.capitalize()}Control()')

# env_control = wifi_yaml.get_note('env_control')

# 初始化 衰减 & 转台 对象
if rf_needed:
    # 读取衰减 配置
    rf_step_list = []
    rf_ip = ''
    model = wifi_yaml.get_note('rf_solution')['model']
    if model != 'RADIORACK-4-220' and model != 'RC4DAT-8G-95':
        raise EnvironmentError("Doesn't support this model")

    if model == 'RADIORACK-4-220':
        rf_ip = wifi_yaml.get_note('rf_solution')[model]['ip_address']
    if model == 'RC4DAT-8G-95':
        rf_ip = '192.168.50.19'

    logging.info('test rf')
    rf_tool = TelnetInterface(rf_ip)
    logging.info(f'rf_ip {rf_ip}')
    rf_step_list = wifi_yaml.get_note('rf_solution')['step']
    rf_step_list = [i for i in range(*rf_step_list)][::8]
    logging.info(f'rf_step_list {rf_step_list}')

if corner_needed:
    corner_step_list = []
    # 配置衰减
    corner_ip = wifi_yaml.get_note('corner_angle')['ip_address']

    logging.info('test corner')
    corner_tool = TelnetInterface(corner_ip)
    logging.info(f'corner_ip {corner_ip}')
    corner_step_list = wifi_yaml.get_note('corner_angle')['step']
    corner_step_list = [i for i in range(*corner_step_list)][::45]
    logging.info(f'corner step_list {corner_step_list}')

step_list = [1]
if rf_needed and rf_step_list:
    step_list = rf_step_list
if corner_needed and corner_step_list:
    step_list = corner_step_list
if rf_needed and corner_needed and rf_step_list and corner_step_list:
    step_list = itertools.product(corner_step_list, rf_step_list)

logging.info(f'finally step_list {step_list}')

# 配置 测试报告
pytest.testResult.x_path = [] if (rf_needed and corner_needed) == 'both' else step_list
pytest.testResult.init_rvr_result()
rx_result, tx_result = '', ''


def modify_tcl_script(old_str, new_str):
    file = './script/rvr.tcl'
    with open(file, "r", encoding="utf-8") as f1, open("%s.bak" % file, "w", encoding="utf-8") as f2:
        for line in f1:
            if old_str in line:
                line = new_str
            f2.write(line)
    os.remove(file)
    os.rename("%s.bak" % file, file)


def iperf_on(command, adb, direction='tx'):
    if os.path.exists(f'rvr_log_{pytest.dut.serialnumber}.txt') and '-s' in command:
        for proc in psutil.process_iter():
            try:
                files = proc.open_files()
                for f in files:
                    if f.path == f'rvr_log_{pytest.dut.serialnumber}.txt':
                        proc.kill()  # Kill the process that occupies the file
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        os.remove(f'rvr_log_{pytest.dut.serialnumber}.txt')

    def server_on():
        logging.info(f'server {command} ->{adb}<-')
        if adb and pytest.connect_type == 'telnet':
            pytest.dut.checkoutput(command)
        else:
            with open(f'rvr_log_{pytest.dut.serialnumber}.txt', 'w') as f:
                popen = subprocess.Popen(command.split(), stdout=f, encoding='utf-8')
            return popen
        # logging.info(subprocess.run('tasklist | findstr "iperf"'.replace('iperf',pc_ipef),shell=True,encoding='gbk'))
        # logging.info(pytest.dut.checkoutput('ps -A|grep "iperf"'.replace('iperf',dut_iperf)))

    if adb:
        if test_tool == 'iperf3':
            command = 'iperf3 -s -1'
        if pytest.connect_type == 'adb':
            command = f'adb -s {adb} shell ' + command
    else:
        if test_tool == 'iperf3':
            command = f'iperf3 -c {pytest.dut.dut_ip} -i1 -t30 -P5'
            if direction == 'tx':
                command = f'iperf3 -c {pytest.dut.dut_ip} -i1 -t30 -P5 -R'

    logging.info(f'command {command} ->{adb}<-')

    if re.findall(r'iperf[3]?.*?-s', command):
        popen = server_on()
    else:
        if adb and pytest.connect_type == 'telnet':
            pytest.dut.checkoutput(command)
        popen = subprocess.Popen(command.split(), encoding='utf-8')
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
        pytest.dut.tn.close()


def get_logcat(pair, adb):
    # pytest.dut.kill_iperf()
    # 分析 iperf 测试结果
    result_list = []
    if os.path.exists(f'rvr_log_{pytest.dut.serialnumber}.txt'):
        with open(f'rvr_log_{pytest.dut.serialnumber}.txt', 'r') as f:
            for line in f.readlines():
                logging.info(f'line : {line.strip()}')
                if pair != 1:
                    if '[SUM]' not in line:
                        continue
                if re.findall(r'.*?\d+\.\d*-\s*\d+\.\d*.*?(\d+\.*\d*)\s+Mbits/sec.*?', line.strip(), re.S):
                    result_list.append(
                        float(
                            re.findall(r'.*?\d+\.\d*-\s*\d+\.\d*.*?(\d+\.*\d*)\s+Mbits/sec.*?', line.strip(), re.S)[0]))

    if result_list:
        logging.info(f'{sum(result_list) / len(result_list)}')
        logging.info(f'{result_list}')
        result = sum(result_list) / len(result_list)
    else:
        result = 0
    return round(result, 1)


def push_iperf():
    if iperf_tool and pytest.connect_type == 'adb' and (
            pytest.dut.checkoutput('[ -e /system/bin/iperf ] && echo yes || echo no').strip() != 'yes'):
        path = os.path.join(os.getcwd(), 'res/iperf')
        pytest.dut.push(path, '/system/bin')
        pytest.dut.checkoutput('chmod a+x /system/bin/iperf')


@pytest.fixture(scope='session', autouse=True, params=test_data)
def wifi_setup_teardown(request):
    global rx_result, tx_result, pc_ip, dut_ip
    logging.info('==== wifi env setup start')

    # 重置衰减&转台
    # 衰减器置0
    if rf_needed:
        logging.info('Reset rf value')
        rf_tool.execute_rf_cmd(0)
        logging.info(rf_tool.get_rf_current_value())
        time.sleep(30)

    # 转台置0
    if corner_needed:
        logging.info('Reset corner')
        corner_tool.set_turntable_zero()
        logging.info(corner_tool.get_turntanle_current_angle())
        time.sleep(3)

    # push_iperf()
    router_info = request.param
    if router_needed:
        # 修改路由器配置
        assert router.change_setting(router_info), "Can't set ap , pls check first"
        band = '5 GHz' if '2' in router_info.band else '2.4 GHz'
        ssid = router_info.ssid + "_bat";
        router.change_setting(Router(band=band, ssid=ssid))
        time.sleep(10)

    logging.info('wifi env set done')
    with open(pytest.testResult.detail_file, 'a', encoding='utf-8') as f:
        f.write(f'Testing {router_info} \n')

    if pytest.connect_type == 'telnet':
        connect_status = True
        if router_needed:
            time.sleep(30)
    else:
        # 连接 网络 最多三次重试
        for _ in range(3):
            if not router_needed:
                break
            try:
                type = 'wpa3' if 'WPA3' in router_info.authentication_method else 'wpa2'
                if router_info.authentication_method.lower() in \
                        ['open', '不加密', '无', 'open system', '无加密(允许所有人连接)', 'none']:
                    logging.info('no passwd')
                    cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, "open", "")
                else:
                    cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, type,
                                                             router_info.wpa_passwd)
                if router_info.hide_ssid == '是':
                    cmd += pytest.dut.CMD_WIFI_HIDE

                pytest.dut.checkoutput(cmd)
                time.sleep(5)
                dut_info = pytest.dut.checkoutput('ifconfig wlan0')
                logging.info(dut_info)
                dut_ip = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', dut_info, re.S)
                if dut_ip:
                    dut_ip = dut_ip[0]
                logging.info(f'dut ip address {dut_ip}')
                if pytest.dut.wait_for_wifi_address(target=re.findall(r'(\d+\.\d+\.\d+\.)', dut_ip)[0]):
                    connect_status = True
                    break
            except Exception as e:
                logging.info(e)
                connect_status = False

    if pytest.connect_type == 'telnet':
        dut_ip = pytest.dut.ip
    logging.info(f'dut_ip:{dut_ip}')
    connect_status = True
    if pytest.win_flag:
        ipfoncig_info = pytest.dut.checkoutput_term('ipconfig').strip()
        pc_ip = re.findall(r'IPv4 地址.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
    else:
        ipfoncig_info = pytest.dut.checkoutput_term('ifconfig')
        pc_ip = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
    logging.info(f'pc_ip:{pc_ip}')
    logging.info('==== wifi env setup done')

    if rvr_tool == 'ixchariot':
        if '5' in router_info.band:
            modify_tcl_script("set script ",
                              'set script "$ixchariot_installation_dir/Scripts/High_Performance_Throughput.scr"\n')
        else:
            modify_tcl_script("set script ",
                              'set script "$ixchariot_installation_dir/Scripts/Throughput.scr"\n')
        pytest.dut.checkoutput(pytest.dut.IX_ENDPOINT_COMMAND)
        time.sleep(3)

    yield connect_status, router_info
    # 后置动作
    kill_iperf()
    if rf_needed:
        logging.info('Reset rf value')
        rf_tool.execute_rf_cmd(0)
        logging.info(rf_tool.get_rf_current_value())
        time.sleep(10)
    # 重置结果
    # if len(tx_result_list) == 3 and router_info.data_row !='0':
    #     writeInExcelArea(rx_result_list, row_num=int(router_info.data_row), col_num=10)
    #     writeInExcelArea(tx_result_list, row_num=int(router_info.data_row) + 1, col_num=10)

    # rvr_xlsx.save(filename)
    # if not router_debug:
    #     router.router_control.driver.quit()


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

def kill_iperf():
    # kill iperf
    if rvr_tool == 'iperf':
        try:
            pytest.dut.subprocess_run(pytest.dut.IPERF_KILL.replace('iperf', test_tool))
        except Exception:
            ...
        if pytest.win_flag:
            pytest.dut.popen_term(pytest.dut.IPERF_WIN_KILL.replace('iperf', test_tool))
        else:
            pytest.dut.popen_term(pytest.dut.IPERF_KILL.replace('iperf', test_tool))


def get_tx_rate(pc_ip, dut_ip, device_number, router_info, pair, freq_num, rssi_num, type, corner_set='', db_set=''):
    global tx_result
    tx_result_list = []
    # 最多三次 重试机会
    for _ in range(5):
        logging.info('run tx ')
        tx_result = 0
        mcs_tx = 0
        # pytest.dut.checkoutput(pytest.dut.CLEAR_DMESG_COMMAND)
        # pytest.dut.checkoutput(pytest.dut.MCS_TX_KEEP_GET_COMMAND)
        # kill iperf
        if rvr_tool == 'iperf':
            kill_iperf()
            time.sleep(1)
            if test_tool == 'iperf3':
                adb_popen = iperf_on(tool_path + pytest.dut.IPERF_CLIENT_REGU[type]['tx'].format(
                    pc_ip,
                    pytest.dut.IPERF_TEST_TIME,
                    pair if type == 'TCP' else 1), device_number)
                pc_popen = iperf_on(pytest.dut.IPERF_SERVER[type], '')
            else:
                pc_popen = iperf_on(pytest.dut.IPERF_SERVER[type], '')
                time.sleep(2)
                adb_popen = iperf_on(tool_path + pytest.dut.IPERF_CLIENT_REGU[type]['tx'].format(
                    pc_ip,
                    pytest.dut.IPERF_TEST_TIME,
                    pair if type == 'TCP' else 1), device_number)

            time.sleep(pytest.dut.IPERF_WAIT_TIME)
            if pytest.connect_type == 'telnet':
                time.sleep(15)
            time.sleep(3)
            server_off(adb_popen)
            server_off(pc_popen)
            tx_result = get_logcat(pair if type == 'TCP' else 1, device_number)

        if rvr_tool == 'ixchariot':
            ix.ep1 = dut_ip
            ix.ep2 = pc_ip
            ix.pair = pair
            tx_result = ix.run_rvr()

        if tx_result == False:
            logging.info("Connect failed")
            if rvr_tool == 'ixchariot':
                pytest.dut.checkoutput(pytest.dut.STOP_IX_ENDPOINT_COMMAND)
                time.sleep(1)
                pytest.dut.checkoutput(pytest.dut.IX_ENDPOINT_COMMAND)
                time.sleep(3)
            continue

        mcs_tx = pytest.dut.get_mcs_tx()
        logging.info(f'expected rate {router_info.expected_rate.split()[0]}')
        logging.info(f'{tx_result}, {mcs_tx}')
        tx_result_list.append(tx_result)
        if len(tx_result_list) > 0:
            break
    corner = corner_tool.get_turntanle_current_angle() if corner_needed else corner_set
    tx_result_info = (
        f'{device_number} Throughput Standalone NULL Null {router_info.wireless_mode.split()[0]} '
        f'{router_info.band.split()[0]} {router_info.bandwidth.split()[0]} Rate_Adaptation '
        f'{router_info.channel} {type} UL NULL NULL {db_set} {rssi_num} {corner} NULL '
        f'{mcs_tx if mcs_tx else "NULL"} {",".join(map(str, tx_result_list))}')
    logging.info(tx_result_info)
    pytest.testResult.save_result(tx_result_info.replace(' ', ','))
    with open(pytest.testResult.detail_file, 'a') as f:
        f.write(f'Tx {type} result : {tx_result}\n')
        f.write('-' * 40 + '\n\n')
    return tx_result_list


def get_rx_rate(pc_ip, dut_ip, device_number, router_info, pair, freq_num, rssi_num, type, corner_set='', db_set=''):
    rx_result_list = []
    for _ in range(5):
        logging.info('run rx ')
        rx_result = 0
        mcs_rx = 0
        # clear mcs data
        # pytest.dut.checkoutput(pytest.dut.CLEAR_DMESG_COMMAND)
        # pytest.dut.checkoutput(pytest.dut.MCS_RX_CLEAR_COMMAND)
        # kill iperf
        if rvr_tool == 'iperf':
            kill_iperf()
            time.sleep(1)
            adb_popen = iperf_on(tool_path + pytest.dut.IPERF_SERVER[type], device_number)
            time.sleep(2)
            pc_popen = iperf_on(
                pytest.dut.IPERF_CLIENT_REGU[type]['rx'].format(
                    dut_ip, pytest.dut.IPERF_TEST_TIME,
                    pair if type == 'TCP' else 4), '', direction='rx')
            time.sleep(pytest.dut.IPERF_WAIT_TIME)
            if pytest.connect_type == 'telnet':
                time.sleep(15)
            server_off(adb_popen)
            server_off(pc_popen)
            rx_result = get_logcat(pair if type == 'TCP' else 4, device_number)

        if rvr_tool == 'ixchariot':
            ix.ep1 = pc_ip
            ix.ep2 = dut_ip
            ix.pair = pair
            rx_result = ix.run_rvr()

        if rx_result == False:
            logging.info("Connect failed")
            if rvr_tool == 'ixchariot':
                pytest.dut.checkoutput(pytest.dut.STOP_IX_ENDPOINT_COMMAND)
                time.sleep(1)
                pytest.dut.checkoutput(pytest.dut.IX_ENDPOINT_COMMAND)
                time.sleep(3)
            continue
        time.sleep(3)
        logging.info(f'tx result {tx_result}')
        # get mcs data
        mcs_rx = pytest.dut.get_mcs_rx()
        logging.info(f'expected rate {router_info.expected_rate.split()[1]}')
        logging.info(f'{rx_result}, {mcs_rx}')
        rx_result_list.append(rx_result)
        if len(rx_result_list) > 2:
            break
    corner = corner_tool.get_turntanle_current_angle() if corner_needed else corner_set

    rx_result_info = (
        f'{device_number} Throughput Standalone NULL Null {router_info.wireless_mode.split()[0]} '
        f'{router_info.band.split()[0]} {router_info.bandwidth.split()[0]} Rate_Adaptation '
        f'{router_info.channel} {type} DL NULL NULL {db_set} {rssi_num} {corner} NULL '
        f'{mcs_rx if mcs_rx else "NULL"} {",".join(map(str, rx_result_list))}')
    pytest.testResult.save_result(rx_result_info.replace(' ', ','))
    with open(pytest.testResult.detail_file, 'a', encoding='utf-8') as f:
        logging.info('writing')
        f.write(f'Rx {type} result : {rx_result}\n')
        f.write('-' * 40 + '\n\n')
    return rx_result_list


# 测试 iperf
@pytest.mark.repeat(0)
@pytest.mark.parametrize("rf_value", step_list)
def test_wifi_rvr(wifi_setup_teardown, rf_value):
    global rx_result, tx_result, pc_ip, dut_ip
    # 判断板子是否存在  ip
    if not wifi_setup_teardown[0]:
        logging.info("Can't connect wifi ,input 0")
        # rx_result_list.append('0')
        # tx_result_list.append('0')
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write("\n Can't connect wifi , skip this loop\n\n")
        return
    router_info = wifi_setup_teardown[1]

    # 执行 修改 步长
    # 修改衰减
    if rf_needed:
        logging.info(f'set rf value {rf_value}')
        value = rf_value[1] if type(rf_value) == tuple else rf_value
        rf_tool.execute_rf_cmd(value)
        # 获取当前衰减值
        logging.info(rf_tool.get_rf_current_value())

    if corner_needed:
        logging.info('set corner value')
        value = rf_value[0] if type(rf_value) == tuple else rf_value
        corner_tool.execute_turntable_cmd('rt', angle=value * 10)
        # 获取转台角度
        logging.info(corner_tool.get_turntanle_current_angle())

    with open(pytest.testResult.detail_file, 'a') as f:
        f.write('-' * 40 + '\n')
        info, corner_set = '', ''
        db_set = 0
        if rf_needed:
            db_set = rf_value[1] if type(rf_value) == tuple else rf_value
            info += 'db_set : ' + str(db_set) + '\n'

        if corner_needed:
            corner_set = rf_value[0] if type(rf_value) == tuple else rf_value
            info += 'corner_set : ' + str(corner_set) + '\n'

        f.write(info)
    # time.sleep(1)

    # 获取rssi
    for i in range(10):
        rssi_info = pytest.dut.checkoutput(pytest.dut.IW_LINNK_COMMAND)
        logging.info(rssi_info)
        if 'signal' in rssi_info and i > 4:
            break
    else:
        rssi_info = ''

    if 'Not connected' in rssi_info:
        logging.info('The signal strength is not enough ,input 0')
        rx_result, tx_result, rssi_num = 0, 0, 0
        with open(pytest.testResult.detail_file, 'a') as f:
            f.write('signal strength is not enough no rssi \n')
        assert False, "Wifi is not connected"
    logging.info('Start test')

    try:
        rssi_num = int(re.findall(r'signal:\s+(-?\d+)\s+dBm', rssi_info, re.S)[0])
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
    # iperf  打流
    if 'tx' in router_info.test_type:
        # 动态匹配 打流通道数
        pair = wifi_yaml.get_note('rvr')['pair']
        logging.info(f'rssi : {rssi_num} pair : {pair}')
        get_tx_rate(pc_ip, dut_ip, pytest.dut.serialnumber, router_info, pair, freq_num, rssi_num, protocol,
                    corner_set=corner_set,
                    db_set=db_set)
    if 'rx' in router_info.test_type:
        pair = wifi_yaml.get_note('rvr')['pair']
        logging.info(f'rssi : {rssi_num} pair : {pair}')
        get_rx_rate(pc_ip, dut_ip, pytest.dut.serialnumber, router_info, pair, freq_num, rssi_num, protocol,
                    corner_set=corner_set,
                    db_set=db_set)
