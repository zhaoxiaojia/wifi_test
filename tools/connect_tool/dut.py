#!/usr/bin/env python 
# -*- coding: utf-8 -*- 


"""
# File       : dut.py
# Time       ：2023/7/4 15:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""
import logging
import subprocess


class Dut():
    DMESG_COMMAND = 'dmesg -S'
    CLEAR_DMESG_COMMAND = 'dmesg -c'

    SETTING_ACTIVITY_TUPLE = 'com.android.tv.settings', '.MainSettings'
    MORE_SETTING_ACTIVITY_TUPLE = 'com.droidlogic.tv.settings', '.more.MorePrefFragmentActivity'

    SKIP_OOBE = "pm disable com.google.android.tungsten.setupwraith;settings put secure user_setup_complete 1;settings put global device_provisioned 1;settings put secure tv_user_setup_complete 1"
    # iperf 相关命令
    IPERF_TEST_TIME = 30
    IPERF_WAIT_TIME = IPERF_TEST_TIME + 5

    def iperf(args, command='iperf'):
        return f'{command} {args}'

    IPERF_SERVER = {'TCP': iperf(' -s -w 4m -i 1'),
                    'UDP': iperf(' -s -u -i 1 ')}
    IPERF_CLIENT_REGU = {'TCP': {'tx': iperf(' -c {} -w 4m -i 1 -t {} -P{}'),
                                 'rx': iperf(' -c {} -w 4m -i 1 -t {} -P{}')},
                         'UDP': {'tx': iperf(' -c {} -u -i1 -b 800M -t {} -P{}'),
                                 'rx': iperf(' -c {} -u -i1 -b 300M -t {} -P{}')}}

    IPERF_MULTI_SERVER = 'iperf -s -w 4m -i 1 {}&'
    IPERF_MULTI_CLIENT_REGU = '.iperf -c {} -w 4m -i 1 -t 60 -p {}'

    IPERF3_CLIENT_UDP_REGU = 'iperf3 -c {} -i 1 -t 60 -u -b 120M -l63k -P {}'

    IPERF_KILL = 'killall -9 iperf'
    IPERF_WIN_KILL = 'taskkill /im iperf.exe -f'
    IW_LINNK_COMMAND = 'iw dev wlan0 link'
    IX_ENDPOINT_COMMAND = "monkey -p com.ixia.ixchariot 1"
    STOP_IX_ENDPOINT_COMMAND = "am force-stop com.ixia.ixchariot"
    CMD_WIFI_CONNECT = 'cmd wifi connect-network {} {} {}'
    CMD_WIFI_HIDE = ' -h'
    CMD_WIFI_STATUS = 'cmd wifi status'


    WIFI_CONNECT_PACKAGE = 'com.example.wifiConnect'
    WIFI_CONNECT_ACTIVITY = f'am start -n {WIFI_CONNECT_PACKAGE}/.MainActivity'
    WIFI_CONNECT_COMMAND_REGU = 'am start -n com.example.wifiConnect/.MainActivity -e ssid {}'
    WIFI_CONNECT_PASSWD_REGU = ' -e passwd {}'
    WIFI_CONNECT_HIDE_SSID_REGU = ' --ez hide_ssid true -e type {}'
    WIFI_DISCONNECT_COMMAND = WIFI_CONNECT_ACTIVITY + ' --ez disconnect true'
    WIFI_CHANGE_STATUS_REGU = ' -e wifi_status {}'
    WIFI_FORGET_WIFI_STR = ' --ez forget true'
    CMD_WIFI_LIST_NETWORK = "cmd wifi list-networks |grep -v Network |awk '{print $1}'"
    CMD_WIFI_FORGET_NETWORK = 'cmd wifi forget-network {}'

    MCS_RX_GET_COMMAND = 'iwpriv wlan0 get_last_rx'
    MCS_RX_CLEAR_COMMAND = 'iwpriv wlan0 clear_last_rx'
    MCS_TX_GET_COMMAND = 'iwpriv wlan0 get_rate_info'
    MCS_TX_KEEP_GET_COMMAND = "'for i in `seq 1 10`;do iwpriv wlan0 get_rate_info;sleep 6;done ' & "
    POWERRALAY_COMMAND_FORMAT = './tools/powerRelay /dev/tty{} -all {}'

    GET_COUNTRY_CODE = 'iw reg get'
    SET_COUNTRY_CODE_FORMAT = 'iw reg set {}'

    OPEN_INFO = r'<node index="0" text="Hotspot name" resource-id="android:id/title" class="android.widget.TextView" package="com.(.*?).tv.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="true"'
    CLOSE_INFO = r'<node index="0" text="Hotspot name" resource-id="android:id/title" class="android.widget.TextView" package="com.(.*?).tv.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="false"'

    PLAYERACTIVITY_REGU = 'am start -n com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity -d https://www.youtube.com/watch?v={}'
    VIDEO_TAG_LIST = [
        {'link': 'r_gV5CHOSBM', 'name': '4K Amazon'},  # 4k
        {'link': 'vX2vsvdq8nw', 'name': '4K HDR 60FPS Sniper Will Smith'},  # 4k hrd 60 fps
        # {'link': '9Auq9mYxFEE', 'name': 'Sky Live'},
        {'link': '-ZMVjKT3-5A', 'name': 'NBC News (vp9)'},  # vp9
        {'link': 'LXb3EKWsInQ', 'name': 'COSTA RICA IN 4K 60fps HDR (ULTRA HD) (vp9)'},  # vp9
        {'link': 'b6fzbyPoNXY', 'name': 'Las Vegas Strip at Night in 4k UHD HLG HDR (vp9)'},  # vp9
        {'link': 'AtZrf_TWmSc', 'name': 'How to Convert,Import,and Edit AVCHD Files for Premiere (H264)'},  # H264
        {'link': 'LXb3EKWsInQ', 'name': 'COSTA RICA IN 4K 60fps HDR(ultra hd) (4k 60fps)'},  # 4k 60fps
        {'link': 'NVhmq-pB_cs', 'name': 'Mr Bean 720 25fps (720 25fps)'},
        {'link': 'bcOgjyHb_5Y', 'name': 'paid video'},
        {'link': 'rf7ft8-nUQQ', 'name': 'stress video'}
        # {'link': 'hNAbQYU0wpg', 'name': 'VR 360 Video of Top 5 Roller (360)'}  # 360
    ]

    WIFI_BUTTON_TAG = 'Available networks'

    def __init__(self):
        self.serialnumber = 'executer'

    def checkoutput_term(self, command):
        logging.info(f"command:{command}")
        if not isinstance(command, list):
            command = command.split()
        return subprocess.check_output(command, encoding='gbk')

