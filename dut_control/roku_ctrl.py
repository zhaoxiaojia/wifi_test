# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/2/20 15:09
# @Author  : chao.li
# @File    : rokuIr.py
# @Project : kpi_test
# @Software: PyCharm


import logging
import os
import re
import threading
import time
from threading import Thread
from urllib.parse import quote_plus, urlparse
from xml.etree import ElementTree as ET

import pytest
import requests
from roku import Roku

from dut_control.ir import Ir
from tools.connect_tool.telnet_tool import telnet_tool
from tools.yamlTool import yamlTool

COMMANDS = {
    # Standard Keys
    "home": "Home",
    "reverse": "Rev",
    "forward": "Fwd",
    "play": "Play",
    "select": "Select",
    "left": "Left",
    "right": "Right",
    "down": "Down",
    "up": "Up",
    "back": "Back",
    "replay": "InstantReplay",
    "info": "Info",
    "backspace": "Backspace",
    "search": "Search",
    "enter": "Enter",
    "literal": "Lit",
    # For devices that support "Find Remote"
    "find_remote": "FindRemote",
    # For Roku TV
    "volume_down": "VolumeDown",
    "volume_up": "VolumeUp",
    "volume_mute": "VolumeMute",
    # For Roku TV while on TV tuner channel
    "channel_up": "ChannelUp",
    "channel_down": "ChannelDown",
    # For Roku TV current input
    "input_tuner": "InputTuner",
    "input_hdmi1": "InputHDMI1",
    "input_hdmi2": "InputHDMI2",
    "input_hdmi3": "InputHDMI3",
    "input_hdmi4": "InputHDMI4",
    "input_av1": "InputAV1",
    # For devices that support being turned on/off
    "power": "Power",
    "poweroff": "PowerOff",
    "poweron": "PowerOn",
}

SENSORS = ("acceleration", "magnetic", "orientation", "rotation")

# roku_lux = YamlTool(os.getcwd() + '/config/roku/roku_changhong.yaml')
roku_config = yamlTool(os.getcwd() + '/config/config.yaml')
roku_ip = roku_config.get_note("connect_type")['telnet']['ip']
roku_wildcard = roku_config.get_note("connect_type")['telnet']['wildcard']
# roku_ser = roku_config.get_note('dut_serial')

lock = threading.Lock()


def decode_ignore(info):
    info.decode('utf-8', 'backslashreplace_backport') \
        .encode('unicode_escape') \
        .decode('utf-8', errors='ignore') \
        .replace('\\r', '\r') \
        .replace('\\n', '\n') \
        .replace('\\t', '\t')


class roku_ctrl(Roku, Ir):
    _instance = None
    VIDEO_STATUS_TAG = [
        # r'screen size \d+x\d+',  # pal层设置video参数时会调用到set property,给vsink设置下来，包括是否是2k/screen size等
        # r'set source window rect',  # 设置视频窗口的位置和宽高
        # r'v4l_get_capture_port_formats: Found \d+ capture formats',  # 获得解码器可支持的codec类型
        # r'avsync session \d+',  # pal层设置video参数时会调用到set property，给asink设置下来，包括是否等待video以及等待时间等
        # r'ready to paused',  # 切换状态为pause
        # r'output port requires \d+ buffers',  # 申请outputbuffer用于存放es数据
        # r'starting video thread',  # video第一帧送入，开始解码线程
        # r'detected audio sink GstAmlHalAsink',  # 检测是否有audio element
        # r'handle_v4l_event: event.type:\d+, event.u.src_change.changes:\d+',
        # 收到decoder发送的解出第一笔,resolution change 的signal
        # r'v4l_setup_capture_port: capture port requires \d+ buffers',  # 申请buffer用于存放解码后的yuv数据
        # r'video_decode_thread:<video_sink> emit first frame signal ts \d+',  # decoder解出第一帧，向pal层发送first frame的signal
        r'display_engine_show: push frame: \d+',  # push_frame就是decoder解出的yuv数据
        # r'gst_aml_hal_asink_pad_event:<audio_sink> done',  # audio 数据流开始start
        # r'gst_aml_vsink_change_state:<video_sink> paused to playing avsync_paused \d+',
        # rokuo收到video start,就会下发setspeed1，pipeline状态切换为playing，正式起播
        # r'gst_aml_hal_asink_change_state:<audio_sink> paused to playing',
        r'display_thread_func: pop frame: \d+',
        # r'gst_aml_hal_asink_event:<audio_sink> receive eos',
        # r'video_eos_thread:<video_sink> Posting EOS',
        # r'gst_aml_hal_asink_change_state:<audio_sink> ready to null',
        # r'gst_aml_vsink_change_state:<video_sink> ready to null'
    ]
    AUDIO_STATUS_TAG = [
        r'get_position:<audio_sink>',
        # r'aml_audio_hwsync_audio_process'
    ]

    AML_SINK_ERROR_TAG = re.compile(r'gst_caps_new_empty failed|gst_pad_template_new failed|'
                                    r'dec ope fail|can not get formats|can not build caps|invalid dw mode \d+|'
                                    r'Bad screen properties string|Bad source window properties string|'
                                    r'Bad window properties string|not accepting format\(\w+\)|'
                                    r'no memory for codec data size \d+|gst_buffer_map failed for codec data|'
                                    r'fail to create thread|V4L2_DEC_CMD_STOP output fail \d+|'
                                    r'postErrorMessage: code \d+ \(\w+\)|meta data is invalid|'
                                    r'Get mate head error|Metadata oversize \d+ > \d+, please check|'
                                    r'VIDIOC_G_FMT error \d+|cap VIDIOC_STREAMOFF error \d+|'
                                    r'v4l_dec_config failed|fail to get visible dimension \d+|'
                                    r'fail to get cropcap \d+|setup capture fail|streamon failed for output: rc \d+ errno \d+|'
                                    r'fail VIDIOC_DQEVENT \d+|VIDIOC_G_PARM error \d+ rc \d+|'
                                    r'cap VIDIOC_DQBUF fail \d+|start avsync error|VIDIOC_STREAMOFF fail ret:\d+|'
                                    r'set secure mode fail|v4l_dec_dw_config failed|set output format \w+ fail|'
                                    r'setup output fail|can not get output buffer \d+|queuing output buffer failed: rc \d+ errno \d+|'
                                    r'start_video_thread failed|dec open fail|uvm open fail|get capture format fail|'
                                    r'reg event fail|start render fail|invalid para \d+ \d+|free index \d+ fail|'
                                    r'queue cb fail \d+|unable to open file \w+|unable to get pts from: \w+|'
                                    r'fail to open \w+|fail to write \w+ to \w+|set volume fail \d+|stream mute fail:\d+|'
                                    r'invalid sync mode \d+|invalid value:\w+|can not get string|wrong ac4_lang:\w+|'
                                    r'wrong ac4_lang2:\w+|wrong ass type \w+|rate \d+.?\d+ fail|no stream opened|'
                                    r'create av sync fail|segment event not received yet|create timer fail|create thread fail|'
                                    r'out buffer fail \d+|wrong size \d+/\d+|asink open failure|fail to load hw:\d+|'
                                    r'OOM|unsupported channel number:\d+|invalid port:\d+|can not open output stream:\d+|'
                                    r'pause failure:\d+|parse ac4 fail|frame too big \d+|header too big \d+|'
                                    r'trans mode write fail \d+/\d+|drop data \d+/\d+|null pointer')

    def __new__(cls, *args, **kw):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kw)
        return cls._instance

    def __init__(self):
        super(roku_ctrl, self).__init__(roku_ip)
        self.ip = roku_ip
        self.ptc_size, self.ptc_mode = '', ''
        # self.get_kernel_log()
        # self.switch_ir('off')
        self.current_target_array = 'launcher'
        self._layout_init()
        # 用于记录当前 遥控光标所在 控件名称
        self.ir_current_location = ''
        self.logcat_check = False
        logging.info('roku init done')

    def __del__(self):
        logging.info('enter in del')
        self.switch_ir('on')

    def __setattr__(self, key, value):
        if key == 'ir_current_location':
            if 'amp;' in value:
                value = value.replace('amp;', '')
        self.__dict__[key] = value

    def _layout_init(self):
        '''
        存放ui 布局相关位置信息
        形式为二维数组 行列对应ui 控件行列 原点左上角
        Returns:

        '''
        self.layout_media_player_home = [['All', 'Video', 'Audio', 'Photo']]
        self.layout_media_player_help_setting = [['Help'], ['Request media type at startup - [On]'],
                                                 ['Lookup album art on Web - [On]'], ['Display format - [Grid]'],
                                                 ['Autorun - [On]'], ['OK']]

    # self.layout_launcher = [['Home'], ['Live TV'], ['What to Watch'], ['Featured Free'], ['Sports'], ['Search'],
    #                         ['Streaming Store'], ['Settings'], ['Secret Screens'], ['Debug']]
    # self.layout_launcher = [['Home'], ['Save list'], ['Search'], ['Streaming Store'], ['Settings'],
    #                         ['Secret Screens'], ['Debug']]
    # self.layout_launcher_setting = [['Network'], ['Remote controls & devices'], ['Theme'], ['Accessibility'],
    #                                 ['TV picture settings'], ['TV inputs'], ['Audio'], ['Parental controls'],
    #                                 ['Guest Mode'], ['Home screen'], ['Payment method'],
    #                                 ['Apple AirPlay and HomeKit'],
    #                                 ['Legal notices'], ['Privacy'], ['Help'], ['System']]

    def __getattr__(self, name):
        if name not in COMMANDS and name not in SENSORS:
            raise AttributeError(f"{name} is not a valid method")

        def command(*args, **kwargs):
            if name in SENSORS:
                keys = [f"{name}.{axis}" for axis in ("x", "y", "z")]
                params = dict(zip(keys, args))
                self.input(params)
            elif name == "literal":
                for char in args[0]:
                    path = f"/keypress/{COMMANDS[name]}_{quote_plus(char)}"
                    self._post(path)
            elif name == "search":
                path = "/search/browse"
                params = {k.replace("_", "-"): v for k, v in kwargs.items()}
                self._post(path, params=params)
            else:
                if len(args) > 0 and (args[0] == "keydown" or args[0] == "keyup"):
                    path = f"/{args[0]}/{COMMANDS[name]}"
                    logging.info(f'key {args[0]}')
                else:
                    path = f"/keypress/{COMMANDS[name]}"
                    logging.info(f'Press key {COMMANDS[name]}')
                self._post(path)
            if 'time' in kwargs.keys():
                time.sleep(kwargs['time'])

        try:
            return command
        except requests.exceptions.ConnectionError:
            ...
        try:
            return command
        except requests.exceptions.ConnectionError:
            return command

    def capture_screen(self, filename):
        '''
        获取当前ui界面的 屏幕截图
        Args:
            filename:  用于保存的文件名

        Returns:

        '''
        logging.info("\rStart to capture screen ....\r")
        para = {'param-image-type': 'jpeg'}
        url = "http://%s:8060/capture-screen/secret" % (roku_ip)
        r = requests.get(url, json=para)
        response = r.content

        with open(file=filename, mode='wb') as handle:
            handle.write(response)
            handle.close()

    def load_array(self, array_txt):
        '''
        从 layout/xxx.txt 中 解析出二维数组
        Args:
            array_txt:

        Returns:

        '''
        with open(os.getcwd() + f'/config/roku/layout/{array_txt}') as f:
            info = f.readlines()
            arr = [i.strip().split(',') for i in info]
        return arr

    def get_ir_focus(self, filename='dumpsys.xml', secret=False):
        '''
        从roku 服务器获取当前tv 页面的控件 xml
        解析xml 获取 focused="true"
        返回解析 得到的 列表中 最后一个元素
        Returns:

        '''

        if not secret:
            # 默认使用 focus 页面获取光标
            for _ in range(5):
                url = f'http://{roku_ip}:8060/query/focus/secret'
                r = requests.get(url).content.decode('utf-8')
                if 'RoScreenWrapper' in r:
                    # 进入待机模式
                    self.home(time=1)
                    continue
                if 'SGScreen.RMPScene.ComponentController_0.ViewManager_0.ViewStack_0.MediaView_0.Video_' in r:
                    # 悬浮菜单时 不通过这个逻辑处理
                    logging.debug("Don't try to  get index in this way")
                    break
                if 'SGScreen.RMPScene.ComponentController_0.ViewManager_0.ViewStack_0.GridView_0.RenderableNode_0.ZoomRowList_0.RenderableNode_' in r:
                    # media player 不通过这个逻辑处理
                    logging.debug("Don't try to get index in this way")
                    break

                focused = re.findall(r'<text>(.*?)</text>', r)
                logging.info(f'sercet {focused[0]}')
                if focused:
                    self.ir_current_location = focused[0]
                    return focused[0]

        node_list = []
        # 解析 页面布局xml 信息 从中获取 当前遥控器 光标位置
        for child in self._get_xml_root():
            for child_1 in child.iter():
                if child_1.tag == 'ItemDetailsView':
                    for child_2 in child_1.iter():
                        if child_2.tag == 'Label' and child_2.attrib['name'] == 'title':
                            # logging.info(child_2.attrib['text'])
                            if child_2.attrib['text']:
                                if '|' in child_2.attrib['text']:
                                    # 处理 media player audio ui 多文件名描述
                                    self.ir_current_location = child_2.attrib['text'].split('|')[0].strip()
                                else:
                                    self.ir_current_location = child_2.attrib['text']
                                return self.ir_current_location
                if child_1.tag == 'RenderableNode' and child_1.attrib.get('focused') and child_1.attrib[
                    'focused'] == 'true':
                    # 处理 悬浮菜单
                    if child_1.attrib.get('uiElementId') and child_1.attrib['uiElementId'] != 'overlay-root':
                        try:
                            if child_1.find('RadioButtonItem'):
                                self.ir_current_location = \
                                    child_1.find('RadioButtonItem').find('ScrollingLabel').find('Label').attrib['text']
                            if child_1.find('AVRadioButtonItem'):
                                self.ir_current_location = \
                                    child_1.find('AVRadioButtonItem').find('ScrollingLabel').find('Label').attrib[
                                        'text']
                            if child_1.find('LabelListNativeItem'):
                                self.ir_current_location = \
                                    child_1.find('LabelListNativeItem').find('ScrollingLabel').find('Label').attrib[
                                        'text']
                        except AttributeError:
                            continue
                        # logging.info(f'{self.ir_current_location}')
                        return self.ir_current_location
                if child_1.tag == 'Button' and child_1.attrib.get('focused') and child_1.attrib['focused'] == 'true':
                    self.ir_current_location = child_1.find('Label').attrib['text']
                    # logging.info(f'show display {self.ir_current_location}')
                    return self.ir_current_location
                if child_1.tag == 'StandardGridItemComponent':
                    if child_1.attrib.get('focused') and child_1.attrib['focused'] == 'true':
                        # logging.info(child_1.attrib['text'])
                        node_list.append(child_1)
        if node_list:
            self.ir_current_location = node_list[-1].find('LayoutGroup').find('Label').attrib['text']

    def _get_media_process_bar(self, filename='dumpsys.xml'):
        '''
        分析dumpsys.xml 中的信息
        获取播放 界面的 process 值

        Args:
            filename: 待分析的文件

        Returns: 播放进度 单位为妙

        '''
        process_index = '0:0'
        for child in self._get_xml_root():
            for child_1 in child.iter():
                if child_1.tag == 'TrickPlayBar' and not child_1.attrib.get('name'):
                    process_index = child_1.find('Label').attrib['text']
                    logging.info(process_index)
                    logging.info(int(process_index.split(':')[0]) * 60 + int(process_index.split(":")[1]))
                    return int(process_index.split(':')[0]) * 60 + int(process_index.split(":")[1])

    def get_ir_index(self, name, array, fuz_match=False):
        '''
        从布局信息 二维数组中 获取 控件的下标
        Args:
            name: 需要查询的目标 名字
            array: 需要查询的 二维数组
            fuz_match: 是否开启模糊匹配
        Returns:

        '''
        if type(array) == str:
            target_array = self.load_array(self.current_target_array + '.txt')
        else:
            target_array = array
        logging.debug(f"Try to get index of  {name}")
        logging.debug(f'Target array {array}')
        for i in target_array:
            for y in i:
                if fuz_match:
                    logging.info(f'开启模糊匹配 {name} {y}')
                    logging.info(f'开启模糊匹配 {type(name)} {type(y)}')
                    if name in y:
                        logging.debug(f'Get location : {target_array.index(i)}  {i.index(y)} {len(i)}')
                        return (target_array.index(i), i.index(y)), len(i)
                else:
                    if name == y:
                        logging.debug(f'Get location : {target_array.index(i)}  {i.index(y)} {len(i)}')
                        return (target_array.index(i), i.index(y)), len(i)

        logging.warning(f"Can't find such this widget {name}")
        return None

    def ir_navigation(self, target, array, secret=False, fuz_match=False):
        '''
        页面导航

        通过获取页面控件信息, 移动遥控器光标 至目标控件
        Args:
            target: 目标控件
            array: 当前页面布局信息 二维数组
            secret: 是否使用focus获取 当前控件
            fuz_match: 是否开启模糊匹配
        Returns:

        '''
        logging.debug(f'navigation {target}')
        self.get_ir_focus(secret=secret)
        if target in self.ir_current_location:
            # 开启模糊匹配
            target = self.ir_current_location
        current_index, _ = self.get_ir_index(self.ir_current_location, array, fuz_match=fuz_match)
        target_index, list_len = self.get_ir_index(target, array, fuz_match=fuz_match)
        # logging.info(f'current index {current_index} target {target_index}')
        x_step = abs(target_index[0] - current_index[0])
        y_step = abs(target_index[1] - current_index[1])
        if x_step == 0 and y_step == 0:
            logging.info(f'navigation {target} done')
            return True

        if x_step > len(array) / 2:
            for i in range(current_index[0] + len(array) - target_index[0]):
                self.up(time=1)
        else:
            for i in range(x_step):
                self.down(time=1)

        if y_step > list_len / 2:
            for i in range(current_index[1] + len(list_len) - target_index[1]):
                self.left(time=1)
        else:
            for i in range(y_step):
                self.left(time=1)

        return self.ir_navigation(target, array)

    def ir_enter(self, target, array, secret=False, fuz_match=False):
        '''
        导航 遥控器光标至目标 并进入
        Args:
            target:
            array:
            secret:

        Returns:

        '''
        self.ir_navigation(target, array, secret=secret, fuz_match=fuz_match)
        self.select(time=2)

    def media_playback(self, target, array):
        '''
        进入 media player 界面
        Args:
            target:
            array:

        Returns:

        '''
        self.ir_enter(target, array)
        time.sleep(1)
        info = self._get_screen_xml()
        # logging.info(info)
        if 'Play from beginning' in info:
            self.down(time=1)
        self.select(time=1)

    def _get_screen_xml(self, filename='dumpsys.xml'):
        '''
        http://192.168.50.109:8060/query/screen/secret
        从roku 服务器获取当前页面的 控件xml
        Returns:

        '''
        r, focused = '', ''

        for _ in range(5):
            url = f"http://{roku_ip}:8060/query/screen/secret"
            r = requests.get(url).content.decode('utf-8')
            if 'Internal error' not in r:
                break
        with open(file='dumpsys.xml', mode='w', encoding='utf-8') as handle:
            handle.write(r)
        # logging.info(r)
        return r

    def _get_xml_root(self, filename='dumpsys.xml'):
        self._get_screen_xml(filename)
        tree = ET.parse(filename)
        return tree.getroot()

    def wait_for_element(self, element, timeout=60):
        '''
        等待 ui 中刷新出某个界面
        Args:
            element: 目标控件
            timeout: 超时时间

        Returns:

        '''
        start = time.time()
        while element not in self._get_screen_xml():
            time.sleep(1)
            if time.time() - start > timeout:
                logging.warning(f"Can't loading {element}")
                break

    def get_u_disk_file_distribution(self, filename='dumpsys.xml'):
        '''
        解析xml 获取u 盘内 folder 分布 以及 file 分布
        Returns: 二维数组

        '''

        node_list, temp = [], []
        current_file = ''
        for child in self._get_xml_root():
            for child_1 in child.iter():
                # 解析StandardGridItemComponent element
                if child_1.tag == 'StandardGridItemComponent':
                    index = int(child_1.attrib['index'])
                    for child_2 in child_1.iter():
                        # if child_2.tag == 'Poster' and 'poster_' in child_2.attrib['uri']:
                        # 	type = re.findall(r'poster_(.*?)_fhd', child_2.attrib['uri'])[0]
                        if child_2.tag == 'Label' and child_2.attrib['name'] == 'line1':
                            if index == 0:
                                if temp:
                                    node_list.append(temp)
                                temp = []
                            temp.append(child_2.attrib['text'])
        if temp not in node_list:
            node_list.append(temp)
        self.media_player_dumpsys = node_list
        logging.info(f'layout info {self.media_player_dumpsys}')
        return node_list

    def get_launcher_element(self, target_element):
        '''
        获取 launcher 界面的 布局信息
        Args:
            target_element: 需要特殊捕捉的 网页元素

        Returns: 布局信息 二维数组

        '''
        node_list = []
        current_file = ''
        for child in self._get_xml_root():
            for child_1 in child.iter():
                # 解析StandardGridItemComponent element
                if child_1.tag == target_element:
                    index = int(child_1.attrib['index'])
                    for child_2 in child_1.iter():
                        if child_2.tag == 'Label' and 'renderPass' not in child_2.attrib:
                            text = child_2.attrib['text']
                            if text and [text] not in node_list:
                                node_list.append([child_2.attrib['text']])
        logging.info(f'node_list {node_list}')
        return node_list

    @classmethod
    def switch_ir(self, status):
        '''
        红外开关
        Args:
            status: 需要设置的状态

        Returns:

        '''
        ir_command = {
            'on': 'echo 0xD > /sys/class/remote/amremote/protocol',
            'off': 'echo 0x2 > /sys/class/remote/amremote/protocol'
        }
        logging.info(f'Set roku ir {status}')
        pytest.dut.execute_cmd(ir_command[status])

    def set_display_size(self, size):
        '''
        设置 picture size
        Args:
            size: 目标size

        Returns:

        '''
        for _ in range(9):
            if self.get_ir_focus() == size:
                self.ptc_size = size
                self.select(time=1)
                break
            self.down(time=1)
            time.sleep(1)
        else:
            logging.warning(f"Can't set display size into {size}")
        logging.info(f'Current size : {size}')

    def set_display_mode(self, mode):
        '''
        设置 picture mode
        Args:
            mode: 目标mode

        Returns:

        '''
        for _ in range(9):
            if self.get_ir_focus() == mode:
                self.ptc_mode = mode
                self.select(time=1)
                break
            self.down(time=1)
            time.sleep(1)
        else:
            logging.warning(f"Can't set display mode into {mode}")
        logging.info(f'Current mode : {mode}')

    def set_picture_mode(self, mode):
        '''
        mode 为需要设置的  ptc mode 列表
        方法会遍历 mode中 所有元素 依次设置
        Args:
            mode:

        Returns:

        '''
        self.info(time=3)
        # if pytest.light_sensor:
        # 	res = pytest.light_sensor.count_kpi(0, roku_lux.get_note('setting_white')[pytest.panel])
        # 	if not res:
        self.info()
        self.down(time=1)
        self.select(time=1)
        self.down(time=1)
        for i in mode:
            logging.info(f'Try to set picture mode into {i}')
            self.select(time=1)
            if self.ptc_mode != i:
                self.set_display_mode(i)
        self.back(time=1)
        self.back(time=1)

    def set_picture_size(self, size):
        '''
        size 为需要设置的  ptc size 列表
        方法会遍历 size中 所有元素 依次设置
        Args:
            size:

        Returns:

        '''
        self.info(time=3)
        # if pytest.light_sensor:
        # 	res = pytest.light_sensor.count_kpi(0, roku_lux.get_note('setting_white')[pytest.panel])
        # 	if not res:
        self.info()
        self.down(time=1)
        self.select(time=1)
        self.down(time=1)
        self.down(time=1)
        self.select(time=1)
        for _ in range(6):
            self.down(time=1)
        for i in size:
            logging.info(f'Try to set picture size into {i}')
            self.select(time=1)
            if self.ptc_size != i:
                self.set_display_size(i)
        self.back(time=1)
        self.back(time=1)
        self.back(time=1)

    def set_caption_status(self, status):
        '''
        status 为需要设置的 字幕状态
        Returns:

        status 集合 On always,On replay,On mute,Off
        '''
        if status not in ['On always', 'On replay', 'On mute', 'Off']:
            raise ValueError(f"Does't support this {status}")
        self.info(time=3)
        for _ in range(3):
            self.down(time=1)
        self.select(time=1)
        self.select(time=1)
        for _ in range(6):
            if self.get_ir_focus() != status:
                self.down(time=1)
                continue
            self.select(time=1)
            break
        else:
            logging.warning(f"Can't set caption to {status}")

    def set_caption(self, language):
        '''
        设置字幕
        前提条件 字幕 需要被打开
        Args:
            language:

        Returns:

        '''
        for _ in range(3):
            if 'TV settings' in self._get_screen_xml():
                break
            self.info(time=3)
        for _ in range(3):
            self.down(time=1)
        self.select(time=1)
        self.down(time=1)
        self.select(time=1)
        for _ in range(10):
            index = self.get_ir_focus()
            logging.info(f'index {index}')
            if index != language:
                self.down(time=1)
                continue
            self.select(time=1)
            break
        else:
            logging.warning(f"Can't set language {language}")

    def get_dmesg_log(self):
        '''
        获取 dmesg 相关打印 存至 dmesg.log
        Returns:

        '''
        with open('dmesg.log', 'a') as f:
            info = pytest.dut.checkoutput('dmesg')
            f.write(info)
        pytest.dut.checkoutput('dmesg -c')

    def get_kernel_log(self, filename='kernel.log'):
        '''
        新开一个 thread 获取8070 端口的 kernel 信息
        Args:
            filename: 用于保存打印的文件名

        Returns:

        '''

        def run_logcast(filename):
            while True:
                info = tl.tn.read_very_eager()
                if info != b'':
                    with open(filename, 'a', encoding='utf-8') as f:
                        try:
                            info = info.decode('utf-8').replace('\r\n', "\n")
                        except Exception as e:
                            info = ''
                        f.write(info)

        logging.info('start telnet 8080 to caputre kernel log ')
        tl = telnet_tool(self.ip, 'sandia')
        info = tl.execute_cmd(f'telnet {self.ip} 8080', wildcard=b'onn. Roku TV')
        # logging.info(info)
        tl.execute_cmd('logcast start')
        time.sleep(1)
        tl.execute_cmd('\x03')  # ,wildcard=b'Console')
        time.sleep(1)
        tl.execute_cmd('\x1A')
        time.sleep(1)
        tl.execute_cmd(f'telnet {self.ip} 8070')
        t = Thread(target=run_logcast, args=(filename,))
        t.daemon = True
        t.start()

    def analyze_logcat(self, re_list, timeout=10):
        '''
        dut 需配置 autostart 文件
        push autostart 文件
        1. 创建文件加mkdir -p /nvram/debug_over/etc
        2. cp /etc/autostart /nvram/debug_overlay/etc
        3. vi /nvram/debug_overlay/etc/autostart
        4. export GST_DEBUG=2,amlvsink:6,amlhalasink:6
        5. 重启 dut
        Args:
            re_list:

        Returns:

        '''
        import copy
        target_list = copy.deepcopy(re_list)
        # tl = TelnetTool(self.ip, pytest.dut.wildcard)
        pytest.dut.execute_cmd('\x03')
        pytest.dut.execute_cmd('\x03')
        pytest.dut.execute_cmd('logcat')
        start = time.time()
        temp = []
        while (time.time() - start < timeout):
            data = pytest.dut.tn.read_eager()
            if data:
                data = data.decode()
            else:
                continue
            if '\n' in data:
                for i in data.split('\n')[:-1]:
                    temp.append(i)
                    info = ''.join(temp)
                    with open('logcat.log', 'a') as f:
                        f.write(info)

                    temp.clear()
                temp.append(data.split('\n')[-1])
            else:
                temp.append(data)
        with open('logcat.log', 'r') as f:
            for i in f.readlines():
                if not target_list:
                    return
                if target_list and re.findall(target_list[0], i):
                    logging.info(i)
                    target_list.pop(0)
            else:
                assert False, "Can't catch target log"

    def catch_err(self, filename, tag_list):
        '''

        Args:
            filename:  需要检测的log文件
            tag_list: 需要捕捉的 关键字 正则表达是

        检测到正则时会通过 logging 输出
        Returns:

        '''
        logging.info(f'Start to catch err. Logfile :{filename}')
        with open(filename, 'r') as f:
            info = f.readlines()
        for i in info:
            res = tag_list.findall(i)
            if res:
                logging.warning(res)
        logging.info('Catch done')

    def shutdown(self):
        count = 0
        while pytest.light_sensor.check_backlight():
            # shut down the dut before test
            self.send('power', 10)
            if count > 5:
                raise EnvironmentError("Pls check ir control")

    def get_hdmirx_info(self, **kwargs):
        '''
        获取 hdmirx 相关信息
        Args:
            **kwargs:

        Returns:

        '''
        logging.info(f'hdmirx for expect : {kwargs}')

        def match(info):
            res = re.findall(
                r'Hactive|Vactive|Color Depth|Frame Rate|TMDS clock|HDR EOTF|Dolby Vision|HDCP Debug Value|HDCP14 state|HDCP22 state|Color Space',
                info)
            if res:
                return res

        for _ in range(3):
            try:
                info = pytest.dut.checkoutput('cat /sys/class/hdmirx/hdmirx0/info')
            # info = pytest.dut.checkoutput('dmesg')
            # pytest.dut.checkoutput('dmesg -c')
            except Exception:
                info = ''
            if 'HDCP1.4 secure' in info:
                break
            time.sleep(2)

        logging.info(info)
        info = [i.strip() for i in info.split('\n') if match(i)]
        logging.info(' ,'.join(info[:5]))
        logging.info(' ,'.join(info[5:]))
        result = {i.split(':')[0].strip(): i.split(':')[1].strip() for i in info}
        for k, v in kwargs.items():
            if k == 'depth':
                k = 'Color Depth'
            if k == 'space':
                k = 'Color Space'
            if k == 'frame':
                k = 'Frame Rate'
                if int(result[k]) not in range(*v):
                    logging.warning(f'{result[k]} not in expect , should in {v}')
                    return False
            else:
                if result[k] != v:
                    logging.warning(f'{result[k]} not in expect , should be {v}')
                    return False
        else:
            return True

    def enter_media_player(self):
        '''
        进入 media player
        Returns:

        '''
        self['2213'].launch()
        count = 0
        while True:
            if 'Media Type Selection' in self._get_screen_xml():
                logging.info('enter done')
                return
            self.back(time=1)
            if count > 5:
                logging.warning("Can't open media player")
            time.sleep(3)

    def check_udisk(self):
        '''
        在media player 界面内 检测是否 外接u盘
        dumpsys 当前页面
        判断是否存在 Connecting to a DLNA Media Server or USB Device 字样
        Returns:

        '''
        return 'Select Media Device' in self._get_screen_xml()

    def enter_wifi(self):
        '''
        通过ui导航 Settings -> Network
        Returns:

        '''
        self.ir_enter('Settings', self.get_launcher_element('LabelListNativeItem'))
        self.ir_enter('Network', self.get_launcher_element('ArrayGridItem'))

    def check_conn(self):
        '''
        通过ui导航 Setting -> Network -> Check connection
        Returns:

        '''
        self.enter_wifi()
        self.ir_enter('Check connection', self.get_launcher_element('LabelListItem'))
        for _ in range(20):
            if 'Connection check was successful' in self._get_screen_xml():
                return True
            time.sleep(2)
        else:
            return False

    def setup_conn(self):
        '''
        通过ui导航 Setting -> Network -> Set up connection
        Returns:

        '''
        self.enter_wifi()
        self.ir_enter('Set up connection', self.get_launcher_element('LabelListItem'))
        if self.get_ir_focus() != 'Wireless':
            self.down(time=1)
        logging.info('check wireless')
        assert 'Wireless' == self.get_ir_focus(), "Can't found wireless "
        self.select(time=1)
        self.select(time=1)
        for _ in range(20):
            if 'Scan again to see all network' in self._get_screen_xml():
                break
            time.sleep(2)
        else:
            assert False, "Can't load wifi scan list"

    def _wifi_scan(self, ssid):
        '''
        通过ui导航 Setting -> Network -> Scan again to see all network
        Args:
            ssid:  目标ssid

        Returns:

        '''
        for _ in range(5):
            if ssid in self._get_screen_xml():
                break
            self.ir_enter('Scan again to see all networks', self.get_launcher_element('ArrayGridItem'))
            return True
        else:
            return False
            logging.info(f"Can't find target ssid {ssid}")

    def wifi_conn(self, ssid, pwd='', band=5):
        '''
        通过ui导航 Setting -> Network -> 目标ssid
        Args:
            ssid:
            pwd:
            band:

        Returns:

        '''
        self.setup_conn()
        self._wifi_scan(ssid)
        self.ir_enter(ssid, self.get_launcher_element('ArrayGridItem'), fuz_match=True)
        if 'Recommended network found' in self._get_screen_xml():
            # 选择推荐
            if band == 2:
                self.down(time=1)
            self.select(time=1)
        if 'Enter the network password for' in self._get_screen_xml():
            # 填写ssid
            if 'Connect' == self.get_ir_focus():
                # 已经连接过的ssid
                self.down(time=1)
                self.select(time=1)
                self.up(time=1)
                self.up(time=1)
            self.literal(pwd)
            time.sleep(1)
            for _ in range(4):
                self.down(time=1)

        self.select(time=1)
        time.sleep(20)
