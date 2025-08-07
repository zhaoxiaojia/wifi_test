#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2022/11/8 13:57
# @Author  : chao.li
# @Site    :
# @File    : test_Wifi_Sanity_Compatibility.py
# @Software: PyCharm


import csv
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from src.tools.router_tool.AsusRouter.Asusax5400Control import Asusax5400Control
from src.tools.router_tool.AsusRouter.Asusax6700Control import Asusax6700Control
from src.tools.router_tool.H3CBX54Control import H3CBX54Control
from src.tools.router_tool.Linksys1200acControl import Linksys1200acControl
# from tools.router_tool.NetgearR6100Control import NetgearR6100Control
from src.tools.router_tool.Tplink.TplinkAx6000Control import TplinkAx6000Control
from src.tools.router_tool.Tplink.TplinkWr842Control import TplinkWr842Control
from src.tools.router_tool.Xiaomi.Xiaomiax3000Control import Xiaomiax3000Control
from src.tools.router_tool.ZTEax5400Control import ZTEax5400Control

# import threadpool


lock = threading.Lock()
devices_list = ['ap2226cf6a2516052d6aa']
# pool = threadpool.ThreadPool(len(devices_list))
test_data = []

# 读取 测试配置
# 配置文件需以 路由器类型命令
# 测试文件中 不允许 出现空行
# with open(os.getcwd() + '/config/test_data/zteax5400.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]
#
# with open(os.getcwd() + '/config/test_data/linksys1200ac.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]

# with open(os.getcwd() + '/config/test_data/asusax5400.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]

# with open(os.getcwd() + '/config/test_data/h3cbx54.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]
#
with open(os.getcwd() + '/config/test_data/tplinkax6000.csv', 'r') as f:
    reader = csv.reader(f)
    test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]

# with open(os.getcwd() + '/config/test_data/xiaomiax3000.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]

# with open(os.getcwd() + '/config/test_data/tplinkwr842.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]

with open(os.getcwd() + '/config/test_data/asusea6700.csv', 'r') as f:
    reader = csv.reader(f)
    test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]

# with open(os.getcwd() + '/config/test_data/netgearR6100.csv', 'r') as f:
#     reader = csv.reader(f)
#     test_data += [Router(*[i.strip() for i in row]) for row in reader][1:]

# router 控制器
router = ''
wifi = WifiTestApk()
wifi.pc_ip = wifi.checkoutput_term('ifconfig enp3s0 |egrep -o "inet [^ ]*"|cut -f 2 -d \ ').strip()
target_ip = ''
rerun_times = 1
# 修改测试用例名称 以便在测试结果中 确认信息
task_ids = [i.__str__().replace(' ', '_').replace('/', '_') for i in test_data]

# 根据 测试result 根目录 实例 wificompatibility
wifiResult = WifiCompatibilityResult(pytest.result_dir)


# 全局前置以及后置动作 只运行一次
@pytest.fixture(scope='session', autouse=True)
def wifi_save_result():
    ...
    yield
    wifiResult.write_to_excel()
    for i in threading.enumerate():
        logging.info(i.name)
        logging.info(i.__dict__)


# 测试前置以及后置动作 每次测试都会被调用
@pytest.fixture(autouse=True, params=test_data, ids=task_ids,scope='session')
def wifi_setup_teardown(request):
    global target_ip, router
    change_result = ''
    for i in devices_list:
        wifi.serialnumber = i
        if not wifi.check_apk_exist('com.example.wifiConnect'):
            wifi.res_manager.get_target('apk/wifiConnect.apk')
            wifi.install_apk('apk/wifiConnect.apk')
            wifi.get_wifi_connect_permission()
        wifi.root()
        if wifi.checkoutput('[ -e /data/iperf ] && echo yes || echo no').strip() != 'yes':
            wifi.push('res/wifi/iperf', '/data/')
            wifi.checkoutput('chmod a+x /data/iperf')
    wifi.app_stop(wifi.WIFI_CONNECT_PACKAGE)
    router_info = request.param
    if int(wifi.getprop('ro.build.version.sdk')) >= 30:
        if 'No' not in wifi.checkoutput('cmd wifi list-networks'):
            networkid = wifi.checkoutput(wifi.CMD_WIFI_LIST_NETWORK).split()
            for i in networkid:
                wifi.checkoutput(wifi.CMD_WIFI_FORGET_NETWORK.format(i))
                start = time.time()
                while wifi.ping(hostname=target_ip):
                    time.sleep(5)
                    if time.time() - start > 30:
                        assert False, 'still connected'
    else:
        wifi.checkoutput(wifi.WIFI_DISCONNECT_COMMAND)
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
        router = Asusax6700Control()
        change_result = router.change_setting(router_info)
        target_ip = '192.168.8.1'
    # if 'NetgearR6100' in router_info.ssid:
    #     router = NetgearR6100Control()
    #     change_result = router.change_setting(router_info)
    #     target_ip = '192.168.9.1'
    wifi.app_stop(wifi.WIFI_CONNECT_PACKAGE)

    if not change_result:
        raise EnvironmentError("router set with error")

    if router_info.hide_ssid != '是':
        wifi.checkoutput('cmd wifi start-scan')
        scan_list = wifi.run_shell_cmd(f'cmd wifi list-scan-results |grep -F "{router_info.ssid}"')[1]
        logging.info(scan_list)
        step = 0
        while ' ' + router_info.ssid + ' ' not in scan_list:
            time.sleep(5)
            logging.info('re scan')
            wifi.checkoutput('cmd wifi start-scan')
            scan_list = wifi.run_shell_cmd(f'cmd wifi list-scan-results |grep -F "{router_info.ssid}"')[1]
            logging.info(scan_list)
            if step > 3:
                change_result = False
                break
            step += 1
    # time.sleep(10)
    # input('please check the network ')
    yield router_info, router, change_result
    # for j in devices_list:
    #     wifi.serialnumber = j
    #     if int(wifi.getprop('ro.build.version.sdk')) >= 30:
    #         if 'No' not in wifi.checkoutput('cmd wifi list-networks'):
    #             networkid = wifi.checkoutput(wifi.CMD_WIFI_LIST_NETWORK).split()
    #             for i in networkid:
    #                 wifi.checkoutput(wifi.CMD_WIFI_FORGET_NETWORK.format(i))
    #                 start = time.time()
    #                 while wifi.ping(hostname=target_ip):
    #                     time.sleep(5)
    #                     if time.time() - start > 30:
    #                         assert False, 'still connected'
    # else:
    #     wifi.checkoutput(wifi.WIFI_DISCONNECT_COMMAND)


# # @pytest.mark.flaky(reruns=5)
# def test_01(wifi_setup_teardown):
#     assert True
#     # num = random.randrange(0, 10)
#     # logging.info(f'coco is so fucking handsome {pytest.reruns_count}')
#     # count = pytest_runtest_makereport
#     # logging.info(f'count is sssssssss {count}')
#     # assert num > 9

def execute_test(device: str, cmd: str, result: str, port: str):
    # def execute_test(*args):
    # device = args[0]
    # cmd = args[1]
    # result = args[2]
    result = result.replace('device', device)
    logging.info(f'adb -s {device} shell {cmd}')

    wifi.checkoutput_term(f'adb -s {device} shell {cmd}')

    # 检测 网络是否 连接
    check_ipaddress = 'ifconfig wlan0 |egrep -o "inet [^ ]*"|cut -f 2 -d :'
    ip_address = wifi.checkoutput_term(f'adb -s {device} shell {check_ipaddress}')
    # logging.info(ip_address)
    step = 0
    while not ip_address:
        ip_address = wifi.checkoutput_term(f'adb -s {device} shell {check_ipaddress}')
        logging.info(f'ip address {device} {ip_address}')
        if step == 8:
            logging.info('repeat command')
            wifi.checkoutput_term(f'adb -s {device} shell {cmd}')
        if step > 20:
            # if pytest.reruns_count == rerun_times + 1:
            with lock:
                logging.info('Fail')
                wifiResult.save_result(result + 'NULL,Fail')
            assert False, 'connected fail'
        if 'cmd wifi' in cmd:
            time.sleep(5)
        else:
            time.sleep(10)
        step += 1
    # 获取 ip 信息
    logging.info(f'ip address {device} {ip_address}')
    # assert wifi.ping(hostname=target_ip),"can't ping "
    # 获取 bitrate 信息
    bitrate = wifi.get_tx_bitrate()
    with lock:
        logging.info('Pass')
        wifiResult.save_result(result + f'{bitrate},Pass')
    # iperf test
    # logging.info(wifi.IPERF_MULTI_SERVER.format(port))
    # wifi.popen_term(wifi.IPERF_MULTI_SERVER.format(port))
    # cmd = wifi.IPERF_MULTI_CLIENT_REGU.format(wifi.pc_ip, port)
    # logging.info(f'adb -s {device} shell {cmd}')
    # iperf_popen = wifi.popen_term(f'adb -s {device} shell {cmd}')
    # start_time = time.time()
    # while True and time.time() - start_time < 65:
    #     try:
    #         line = iperf_popen.stdout.readline()
    #     except UnicodeDecodeError as e:
    #         line = ''
    #     if line:
    #         logging.info(f'{device} : {line}')
    #         print(f'{device} : {line}')
    #     if line is None or '0-60.' in line:
    #         logging.info(f'{device} iperf done')
    #         break
    # # iperf_popen.terminate()
    # logging.info(f'{device} kill iperf')
    # wifi.popen_term(wifi.IPERF_KILL)
    # wifi.popen_term(f'adb -s {device} shell {wifi.IPERF_KILL}')


# @pytest.mark.repeat(3)
@pytest.mark.flaky(reruns=3)
def test_wifi(wifi_setup_teardown, ):
    # 配置result 所需信息

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
        f'{router_info.bandwidth},{router_info.channel},{router_info.authentication},'
        f'{passwd},{router_info.hide_ssid},NULL,')

    # 根据网络 环境选择 连接方式
    if int(wifi.getprop('ro.build.version.sdk')) >= 30 and not router_info.wep_encrypt:
        logging.info('sdk over 30 ')
        type = 'wpa3' if 'WPA3' in router_info.authentication else 'wpa2'
        if router_info.authentication.lower() in \
                ['open', '不加密', '无', 'open system', '无加密(允许所有人连接)', 'none']:
            logging.info('no passwd')
            cmd = wifi.CMD_WIFI_CONNECT_OPEN.format(router_info.ssid)
        else:
            cmd = wifi.CMD_WIFI_CONNECT.format(router_info.ssid, type, passwd)
        if router_info.hide_ssid == '是':
            if int(wifi.getprop('ro.build.version.sdk')) >= 31:
                cmd += wifi.CMD_WIFI_HIDE
            else:
                cmd = (wifi.WIFI_CONNECT_COMMAND_REGU.format(router_info.ssid) +
                       wifi.WIFI_CONNECT_PASSWD_REGU.format(passwd) +
                       wifi.WIFI_CONNECT_HIDE_SSID_REGU.format(router_info.hide_type))
    else:
        logging.info('sdk less then 30')
        if router_info.hide_ssid == '是':
            cmd = (wifi.WIFI_CONNECT_COMMAND_REGU.format(router_info.ssid) +
                   wifi.WIFI_CONNECT_PASSWD_REGU.format(passwd) +
                   wifi.WIFI_CONNECT_HIDE_SSID_REGU.format(router_info.hide_type))
        else:
            cmd = (wifi.WIFI_CONNECT_COMMAND_REGU.format(router_info.ssid) +
                   wifi.WIFI_CONNECT_PASSWD_REGU.format(passwd))
    # 起线程池 进行测试
    with ThreadPoolExecutor(max_workers=len(devices_list)) as pool:
        futures = [pool.submit(execute_test, i, cmd, result, f'500{devices_list.index(i) + 1}') for i in devices_list]
        for j in as_completed(futures):
            j.result()

    # reqs = threadpool.makeRequests(execute_test, [([i, cmd, result], None) for i in devices_list])
    # [pool.putRequest(req) for req in reqs]
    # pool.wait()
    # 根据ping 结果 写入 csv 文件
    # if wifi.ping(hostname=target_ip):
    #     wifiResult.save_result(result + f'{bitrate},Pass')
    # else:
    #     # if pytest.reruns_count == rerun_times + 1:
    #     wifiResult.save_result(result + f'{bitrate},Fail')
    #     assert False, "Can't not ping"
