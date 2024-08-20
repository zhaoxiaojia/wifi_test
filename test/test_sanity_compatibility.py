# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/16 15:26
# @Author  : chao.li
# @File    : test_sanity_compatibility.py


import csv
import logging
import os
import random
import re
import signal
import subprocess
import time

import _io
import pytest


from tools.router_tool.Router import Router
from tools.router_tool.AsusRouter.Asusax5400Control import Asusax5400Control
from tools.router_tool.AsusRouter.Asusea6700Control import Asusea6700Control
from tools.router_tool.H3CBX54Control import H3CBX54Control
from tools.router_tool.Linksys1200acControl import Linksys1200acControl
# from tools.router_tool.NetgearR6100Control import NetgearR6100Control
from tools.router_tool.Tplink.TplinkAx6000Control import TplinkAx6000Control
from tools.router_tool.Tplink.TplinkWr842Control import TplinkWr842Control
from tools.router_tool.Xiaomi.Xiaomiax3000Control import Xiaomiax3000Control
from tools.router_tool.ZTEax5400Control import ZTEax5400Control
from tools.yamlTool import yamlTool
import threading




import pandas as pd

from tools.decorators import singleton
@singleton
class WifiCompatibilityResult:
    '''
    Singleton class,should not be inherited
    handle WiFi compatibility text result

    Attributes:
        logdir : log path
        current_number : current index
        wifi_excelfile : compatibility excel file
        log_file : compatibility result csv

    '''

    def __init__(self, logdir):
        self.logdir = logdir
        self.current_number = 0
        self.wifi_excelfile = f'{self.logdir.split("results")[0]}/results/WifiCompatibilityExcel.xlsx'
        if not hasattr(self, 'logFile'):
            # self.log_file = f'{self.logdir}/WifiCompatibility_' + time.asctime() + '.csv'
            self.log_file = f'{self.logdir}/WifiCompatibility.csv'
        with open(self.log_file, 'a', encoding='utf-8') as f:
            title = 'Serial Ap_Type	SSID Band Wireless_mode	Bandwidth Channel Authentication_Method Passwd Hide_Ssid PMF Theoretical_Rate Result'
            f.write(','.join(title.split()))
            f.write('\n')

    def save_result(self, result):
        '''
        write result to log_file
        @param casename: wifi case name
        @param result: result
        @return: None
        '''
        logging.info('Writing to csv')
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(result)
            f.write('\n')
        logging.info('Write done')

    def write_to_excel(self):
        '''
        format csv to excel
        @return: None
        '''
        logging.info('Write to excel')
        df = pd.read_csv(self.log_file)
        # 转置数据
        # df = pd.DataFrame(df.values.T, index=df.columns, columns=df.index)
        if not os.path.exists(self.wifi_excelfile):
            df.to_excel(self.wifi_excelfile, sheet_name=time.asctime().replace(' ', '_').replace(':', '-'))
        else:
            with pd.ExcelWriter(self.wifi_excelfile, engine='openpyxl', mode='a') as f:
                df.to_excel(f, sheet_name=time.asctime().replace(' ', '_').replace(':', '-'))
        logging.info('Write done')

test_data = []

# 读取 测试配置
# 配置文件需以 路由器类型命令
# 测试文件中 不允许 出现空行
# with open(os.getcwd() + '/config/wifi_compatibility_data/zteax5400.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]
#
# with open(os.getcwd() + '/config/wifi_compatibility_data/linksys1200ac.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]

with open(os.getcwd() + '/config/wifi_compatibility_data/asusax5400.csv', 'r',encoding='utf-8') as f:
    reader = csv.reader(f)
    test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]

# with open(os.getcwd() + '/config/wifi_compatibility_data/h3cbx54.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]
#
# with open(os.getcwd() + '/config/wifi_compatibility_data/tplinkax6000.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]
#
# with open(os.getcwd() + '/config/wifi_compatibility_data/xiaomiax3000.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]
#
# with open(os.getcwd() + '/config/wifi_compatibility_data/tplinkwr842.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]
#
# with open(os.getcwd() + '/config/wifi_compatibility_data/asusea6700.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]
#
# with open(os.getcwd() + '/config/wifi_compatibility_data/netgearR6100.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]

ipfoncig_info = pytest.dut.checkoutput_term('ipconfig').strip()
pytest.dut.pc_ip = re.findall(r'IPv4 地址.*?(\d+\.\d+\.\d+\.\d+)', ipfoncig_info, re.S)[0]
wifiResult = WifiCompatibilityResult(pytest.result_path)
router,target_ip = '',''
task_ids = [i.__str__().replace(' ', '_').replace('/', '_') for i in test_data]


@pytest.fixture(autouse=True, params=test_data, ids=task_ids,scope='session')
def wifi_setup_teardown(request):
    global target_ip, router
    router_info = request.param
    if 'ASUSAX5400' in router_info.ssid:
        router = Asusax5400Control()
        change_result = router.change_setting(router_info)
        target_ip = '192.168.1.1'
    if 'ZTEax5400' in router_info.ssid:
        router = ZTEax5400Control()
        change_result = router.change_setting(router_info)
        target_ip = '192.168.2.1'
    if 'Linksys1200ac' in router_info.ssid:
        router = Linksys1200acControl()
        change_result = router.change_setting(router_info)
        target_ip = '192.168.3.1'
    if 'H3CBX54' in router_info.ssid:
        router = H3CBX54Control()
        change_result = router.change_setting(router_info)
        target_ip = '192.168.4.1'
    if 'Tplinkax6000' in router_info.ssid:
        router = TplinkAx6000Control()
        change_result = router.change_setting(router_info)
        target_ip = '192.168.5.1'
    if 'XiaomiAX3000' in router_info.ssid:
        router = Xiaomiax3000Control()
        change_result = router.change_setting(router_info)
        target_ip = '192.168.6.1'
    if 'Tplinkwr842' in router_info.ssid:
        router = TplinkWr842Control()
        change_result = router.change_setting(router_info)
        target_ip = '192.168.7.1'
    if 'Asusea6700' in router_info.ssid:
        router = Asusea6700Control()
        change_result = router.change_setting(router_info)
        target_ip = '192.168.8.1'
    # if 'NetgearR6100' in router_info.ssid:
    #     router = NetgearR6100Control()
    #     change_result = router.change_setting(router_info)
    #     target_ip = '192.168.9.1'
    if router_info.hide_ssid != '是':
        pytest.dut.checkoutput('cmd wifi start-scan')
        scan_list = pytest.dut.checkoutput(f'cmd wifi list-scan-results |grep -F "{router_info.ssid}"')
        logging.info(scan_list)
        step = 0
        while ' ' + router_info.ssid + ' ' not in scan_list:
            time.sleep(5)
            logging.info('re scan')
            pytest.dut.checkoutput('cmd wifi start-scan')
            scan_list = pytest.dut.checkoutput(f'cmd wifi list-scan-results |grep -F "{router_info.ssid}"')
            logging.info(scan_list)
            if step > 3:
                change_result = False
                break
            step += 1
    yield router_info, router, change_result
    wifiResult.write_to_excel()

# @pytest.mark.flaky(reruns=3)
def test_wifi(wifi_setup_teardown, ):
    # 路由信息
    router_info = wifi_setup_teardown[0]
    # 路由器型号
    router_type = wifi_setup_teardown[1].__class__.__name__[:-7]

    change_result = wifi_setup_teardown[2]
    if not change_result:
        assert False, "ssid can't be found"

    logging.info(router_info)
    # 获取 测试用例中的 密码信息
    passwd = router_info.wep_passwd if router_info.wep_passwd else router_info.wpa_passwd
    passwd = passwd if passwd else "none"
    # 集成 测试结果信息
    result = (
        f'{router_info.serial},device,{router_type},{router_info.ssid},{router_info.band},{router_info.wireless_mode},'
        f'{router_info.bandwidth},{router_info.channel},{router_info.authentication_method},'
        f'{passwd},{router_info.hide_ssid},NULL,')

    type = 'wpa3' if 'WPA3' in router_info.authentication_method else 'wpa2'
    if router_info.authentication_method.lower() in \
            ['open', '不加密', '无', 'open system', '无加密(允许所有人连接)', 'none']:
        logging.info('no passwd')
        cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid,"open","")
    else:
        cmd = pytest.dut.CMD_WIFI_CONNECT.format(router_info.ssid, type, passwd)
    if router_info.hide_ssid == '是':
        cmd += pytest.dut.CMD_WIFI_HIDE

    logging.info(f'cmd wifi: {cmd}')
    pytest.dut.checkoutput(cmd)

    # 检测 网络是否 连接
    check_ipaddress = 'ifconfig wlan0 |egrep -o "inet [^ ]*"|cut -f 2 -d :'
    ip_address = pytest.dut.checkoutput(check_ipaddress)
    # logging.info(ip_address)
    step = 0
    while not ip_address:
        ip_address = pytest.dut.checkoutput(check_ipaddress)
        if step == 4:
            logging.info('repeat command')
            pytest.dut.checkoutput(cmd)
        if step > 9:
            # if pytest.reruns_count == rerun_times + 1:
            logging.info('Fail')
            wifiResult.save_result(result + 'NULL,Fail')
            assert False, 'connected fail'
        time.sleep(5) if 'cmd wifi' in cmd else time.sleep(10)
        step += 1
    # 获取 ip 信息
    logging.info(f'ip address {ip_address}')
    # assert wifi.ping(hostname=target_ip),"can't ping "
    # 获取 bitrate 信息
    bitrate = pytest.dut.get_tx_bitrate()

    logging.info('Pass')
    wifiResult.save_result(result + f'{bitrate},Pass')
