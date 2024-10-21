# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : __init__.py.py
# Time       ：2023/11/22 10:27
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


import logging
import random
import re
import time
from enum import Enum

import pytest
import serial

from tools.connect_tool.uiautomator_tool import UiautomatorTool


class videoLink(Enum):
    # 4k link
    video_4k_link = "http://10.18.7.6/4k50-cctv16.ts"
    # 8k 200M link
    video_8k_200M_link  = "http://10.18.7.6/8K_H265_60p_200Mbps_Scenery.mp4"
    # 8k 130M link
    video_8k_130M_link = "http://10.18.7.6/8K_AVS3_1min.ts"
    # 8k 90M link
    video_8k_90M_link = "http://10.18.7.6/Worldcup_HEVC_AAC_90M_gop25-output.ts"
    # 8k 54M link
    video_8k_54M_link = "http://10.18.7.6/Huawei_Live2_8KH265_30fps_54Mbps_10bit_AAC.ts"


class Iptv:

    WIFI_ACTIVITY_TUPLE = "ctc.android.smart.terminal.settings","com.android.smart.terminal.settings.network.WifiActivity"
    BT_ACTIVITY_TUPLE = "ctc.android.smart.terminal.settings","com.android.amt.bluetooth.BluetoothActivity"
    CTCC_ACTIVITY_TUPLE = "ctc.android.smart.terminal.iptv", "com.amt.app.IPTVActivity"
    # 清空 URL
    CLEAR_URL = "pm clear com.droidlogic.exoplayer2.demo"
    # 调用http视频播放器
    EXO_PLAYER_TUPLE = "com.droidlogic.exoplayer2.demo","com.droidlogic.combineplayer.ui.MainTabActivity"
    # 调出音乐播放器
    MUSIC_PLAYER_TUPLE = "ctc.android.smart.terminal.nativeplayer",".IndexActivity"

    bt_serial = "COM4"

    # 切换ctcc 认证
    CTCC_AUTHENTICATION = "setprop persist.sys.local 1;setprop persist.sys.auth 'http://47.240.34.45:8080/iptvepg/function/index.jsp'"

class Iptv_ctl:

    WIFI_BUTTON_FOCUSED_INFO = '<node index="0" text="" resource-id="ctc.android.smart.terminal.settings:id/wifiap_on_off" class="android.widget.RelativeLayout" package="ctc.android.smart.terminal.settings" content-desc="" checkable="false" checked="false" clickable="false" enabled="true" focusable="true" focused="true" scrollable="false" long-clickable="false" password="false" selected="false" visible-to-user="true" bounds="[720,530][1320,665]">'
    def __init__(self):
        self.ctl = pytest.dut
        self.iptv = Iptv()
        self.ui_tool = UiautomatorTool(self.ctl.serialnumber)
    def init_ser(self):
        self.ser = serial.Serial(self.iptv.bt_serial, 9600)
    def bt_device_press(self):
        if hasattr(self,"ser"):
            self.ser.write(b'\xA0\x01\x01\xA2')
            time.sleep(3)
            self.ser.write(b'\xA0\x01\x00\xA1')

    def check_wifi_status(self):
        return True if self.ctl.wait_element("ctc.android.smart.terminal.settings:id/network_wifi_on","resource-id") else False

    def check_bt_status(self):
        return True if self.ctl.wait_element("ctc.android.smart.terminal.settings:id/bluetooth_name","resource-id") else False

    def start_wifi(self):
        pytest.dut.app_stop(self.iptv.WIFI_ACTIVITY_TUPLE[0])
        pytest.dut.start_activity(*self.iptv.WIFI_ACTIVITY_TUPLE)
        if not self.check_wifi_status():
            if self.WIFI_BUTTON_FOCUSED_INFO in self.ctl.get_dump_info():
                self.ctl.keyevent(23)
            # self.ctl.find_and_tap("关闭","text")
            logging.info('open wifi')
            time.sleep(3)

    def start_bt(self):
        pytest.dut.app_stop(self.iptv.BT_ACTIVITY_TUPLE[0])
        pytest.dut.start_activity(*self.iptv.BT_ACTIVITY_TUPLE)
        if not self.check_bt_status():
            self.ctl.wait_and_tap("蓝牙","text")
            self.ctl.wait_and_tap("开启","text")

    def wait_keyboard(self):
        for i in range(5):
            self.ctl.uiautomator_dump()
            if 'android:id/inputArea' in self.ctl.get_dump_info():  # or \
                # '"com.android.tv.settings:id/guidedactions_item_title" class="android.widget.EditText"' in self.get_dump_info():
                break
            else:
                self.ctl.keyevent(23)
                time.sleep(1)
                self.ctl.uiautomator_dump()
                if '中文' in self.ctl.get_dump_info():
                    self.ctl.find_and_tap('中文','text')
    def find_wifi_ssid(self, ssid):
        self.start_wifi()
        time.sleep(1)
        result = False
        for i in range(100):
            for _ in range(4):
                self.ctl.keyevent(20 if i < 51 else 21)
            if self.ctl.find_and_tap(ssid, 'text') != (-1, -1):
                time.sleep(1)
                logging.info('find done')
                result = True
                break
            if i < 51:
                if self.ctl.find_element('加入其他网络', 'text'):
                    break;
        else:
            result = False

        time.sleep(1)
        assert result, "Can't find ssid"
        logging.info('find ssid done')
        return result
    def find_bt_ssid(self,ssid):
        self.start_bt()
        self.ctl.wait_and_tap("手动搜索","text")
        time.sleep(1)
        result = False
        for i in range(40):
            self.ctl.keyevent(20 if i < 21 else 21)
            if self.ctl.find_and_tap(ssid, 'text') != (-1, -1):
                time.sleep(1)
                logging.info('find done')
                result = True
                break
        else:
            result = False
        return result

    def connect_wifi(self,ssid,passwd=""):
        self.find_wifi_ssid(ssid)
        self.ctl.uiautomator_dump()
        if re.findall(r'\d\d+\.\d\d+\.\d\d+\.\d\d+',self.ctl.get_dump_info(),re.S):
            # 已经 连接
            logging.info('Already connect')
            self.ctl.keyevent(4)
            self.ctl.home()
            return
        if passwd:
            # 需要输入密码
            if self.ctl.find_element("不保存","text"):
                logging.info("Wrong password, forget it and try again")
                self.ctl.wait_and_tap("不保存","text")
                self.ctl.keyevent(23)
            self.wait_keyboard()
            self.ctl.text(passwd)
            self.ctl.wait_and_tap("连接","text")
        else:
            # 不需要输入密码
            self.ctl.wait_and_tap("连接","text")
        self.ctl.wait_for_wifi_address(target="192.168.50")
        self.ctl.home()

    def connect_bt(self,ssid):
        self.find_bt_ssid(ssid)
        self.ctl.wait_and_tap("配对", "text")
        self.ctl.home()

    def forget_wifi(self,ssid):
        self.find_wifi_ssid(ssid)
        self.ctl.wait_and_tap("不保存","text")


    def cancel_bt(self,ssid):
        self.find_bt_ssid(ssid)
        self.ctl.wait_and_tap("取消配对","text")


    def play_exo(self,link):
        self.ctl.checkoutput(self.iptv.CLEAR_URL)
        self.ctl.start_activity(*self.iptv.EXO_PLAYER_TUPLE)
        self.ctl.wait_and_tap("ONLINE PLAY","text")
        self.wait_keyboard()
        self.ctl.uiautomator_dump()
        while link not in self.ctl.get_dump_info():
            self.ui_tool.d2(focused=True).clear_text()
            self.ctl.text(link)
            self.ctl.uiautomator_dump()
        self.ctl.wait_and_tap("PLAY","text")
        time.sleep(60)
        self.ctl.app_stop(self.iptv.EXO_PLAYER_TUPLE[0])

    def set_ctcc_authentication(self):
        self.ctl.checkoutput(self.iptv.CTCC_AUTHENTICATION)

    def play_ctcc(self):

        def playback():
            time.sleep(10)
        def change_channel():
            self.ctl.keyevent(random.randint(19,20))

        def change_pip():
            logging.info("switch pip windows")
            while "按菜单键弹出更多操作" not in self.ctl.get_dump_info():
                self.ctl.keyevent(23)
                self.ctl.uiautomator_dump()
            for _ in range(5):
                change_channel()
                time.sleep(3)
                if random.randint(0,1):
                    playback()
            self.ctl.keyevent(4)
            self.ctl.uiautomator_dump()
            while "按菜单键弹出更多操作" in self.ctl.get_dump_info():
                self.ctl.keyevent(23)
                self.ctl.uiautomator_dump()

        def change_multi():
            logging.info('switch multi windows')
            while "直播" not in self.ctl.get_dump_info():
                self.ctl.keyevent(4)
                self.ctl.uiautomator_dump()
            self.ui_tool.d2.press("down")
            time.sleep(1)
            self.ui_tool.d2.press("down")
            time.sleep(1)
            self.ui_tool.d2.press("right")
            time.sleep(1)
            self.ui_tool.d2.press("right")
            time.sleep(1)
            self.ctl.uiautomator_dump()
            if not '[1352,1248][1916,1600]' in self.ctl.get_dump_info():
                logging.warning("Can't fouces multi player")
                self.ctl.keyevent(4)
                self.ctl.keyevent(4)
                return
            self.ctl.keyevent(23)
            # enter multi player done
            for _ in range(20):
                while '按OK键互换大小屏内容' not in self.ctl.get_dump_info():
                    self.ctl.keyevent(22)
                    self.ctl.uiautomator_dump()
                self.ctl.keyevent(23)
                change_channel()
                if random.randint(0,1):
                    logging.info("playback a few seconds")
                    playback()
                if random.randint(0,1):
                    logging.info("enter full screen playback")
                    self.ui_tool.d2.press("left")
                    self.ctl.keyevent(23)
                    playback()
                    self.ui_tool.d2.press("back")
                    self.ctl.uiautomator_dump()
                    while '按OK键互换大小屏内容' not in self.ctl.get_dump_info():
                        self.ui_tool.d2.press("right")
                        self.ctl.uiautomator_dump()
            self.ui_tool.d2.press("back")
            time.sleep(1)
            self.ui_tool.d2.press("back")
            time.sleep(1)
            self.ctl.uiautomator_dump()
            while "直播" in self.ctl.get_dump_info():
                self.ctl.keyevent(4)
                self.ctl.uiautomator_dump()

        self.ctl.app_stop(self.iptv.CTCC_ACTIVITY_TUPLE[0])
        self.ctl.start_activity(*self.iptv.CTCC_ACTIVITY_TUPLE)
        time.sleep(1)
        self.ctl.uiautomator_dump()
        for _ in range(5):
            if 'IPTV认证数据不完整' not in self.ctl.get_dump_info():
                time.sleep(1)
                self.ctl.uiautomator_dump()
            else:
                break
            raise EnvironmentError("Pls check env")

        change_multi()
        # change_pip()

