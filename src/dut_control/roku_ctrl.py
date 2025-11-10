"""
Roku control utilities.

This module provides helper functions and a subclass of the ``roku.Roku`` class
to interact with Roku devices programmatically.  It includes logic to look
up the device's IP address from a configuration file, decode bytes while
ignoring errors, and extend the base Roku functionality with additional
commands, screen capture, infrared navigation and media playback helpers.
"""

import logging
import os
import re
import threading
import time
from threading import Thread
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET
from typing import Optional

import pytest
import requests
from roku import Roku

from src.tools.connect_tool.serial_tool import serial_tool
from src.tools.connect_tool.telnet_tool import telnet_tool
from src.tools.config_loader import load_config
from src.util.constants import RokuConst
from typing import Annotated


def _get_roku_ip() -> Optional[str]:
    """
    Load the latest Roku IP address from the configuration.

    This helper refreshes the configuration using :func:`load_config` and
    returns the IP address defined under the ``connect_type`` section.  It
    looks for ``Linux`` settings first, falling back to ``telnet`` if
    necessary, and logs the result for debugging purposes.

    Returns
    -------
    Optional[str]
        The configured Roku IP address, or ``None`` if not defined.
    """
    cfg = load_config(refresh=True) or {}
    connect_cfg = cfg.get("connect_type", {})
    linux_cfg = connect_cfg.get("Linux") or connect_cfg.get("telnet") or {}
    ip = linux_cfg.get("ip")
    logging.info(f"Read ROKU IP: {ip}")
    return ip


lock: Annotated[threading.Lock, "A lock used to synchronize operations across threads"] = threading.Lock()


def decode_ignore(info: Annotated[bytes, "Byte string to decode"]):
    """
    Decode a byte string while gracefully handling invalid sequences.

    The implementation decodes the incoming byte array using UTF‑8, replacing
    invalid bytes with their escape codes.  It then encodes back to a byte
    string with ``unicode_escape`` and decodes again, ignoring any remaining
    errors.  Finally, escaped carriage return, line feed and tab sequences are
    converted to their literal counterparts.

    Parameters
    ----------
    info : bytes
        The input byte sequence to decode.

    Returns
    -------
    str
        A decoded string with problematic bytes replaced and common escape
        sequences normalised.
    """
    info.decode('utf-8', 'backslashreplace_backport') \
        .encode('unicode_escape') \
        .decode('utf-8', errors='ignore') \
        .replace('\\r', '\r') \
        .replace('\\n', '\n') \
        .replace('\\t', '\t')


class roku_ctrl(Roku):
    _instance = None
    # Patterns used to identify notable video status log entries.
    VIDEO_STATUS_TAG = [
        r'display_engine_show: push frame: \d+',
        r'display_thread_func: pop frame: \d+',
    ]
    # Patterns used to identify notable audio status log entries.
    AUDIO_STATUS_TAG = [
        r'get_position:<audio_sink>',
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

    def __init__(self, ip: Optional[str] = None):
        """
        Initialize the class instance, set up internal state and construct UI elements if needed.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if ip is None:
            ip = _get_roku_ip()
        super().__init__(ip)
        self.ip = ip
        self.ptc_size, self.ptc_mode = '', ''
        self.current_target_array = 'launcher'
        self._layout_init()
        self.ir_current_location = ''
        self.logcat_check = False
        self._ser = ''

        logging.info('roku init done')

    def __setattr__(self, key, value):
        """
        Execute the setattr   routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if key == 'ir_current_location':
            if 'amp;' in value:
                value = value.replace('amp;', '')
        self.__dict__[key] = value

    def _layout_init(self):
        """
        Execute the layout init routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.layout_media_player_home = [['All', 'Video', 'Audio', 'Photo']]
        self.layout_media_player_help_setting = [['Help'], ['Request media type at startup - [On]'],
                                                 ['Lookup album art on Web - [On]'], ['Display format - [Grid]'],
                                                 ['Autorun - [On]'], ['OK']]

    def __getattr__(self, name):

        """
        Execute the getattr   routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """

        def command(*args, **kwargs):
            """
            Execute the command routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            if name in RokuConst.SENSORS:
                keys = [f"{name}.{axis}" for axis in ("x", "y", "z")]
                params = dict(zip(keys, args))
                self.input(params)
            elif name == "literal":
                for char in args[0]:
                    path = f"/keypress/{RokuConst.COMMANDS[name]}_{quote_plus(char)}"
                    self._post(path)
            elif name == "search":
                path = "/search/browse"
                params = {k.replace("_", "-"): v for k, v in kwargs.items()}
                self._post(path, params=params)
            else:
                if len(args) > 0 and (args[0] == "keydown" or args[0] == "keyup"):
                    path = f"/{args[0]}/{RokuConst.COMMANDS[name]}"
                    logging.info(f'key {args[0]}')
                else:
                    path = f"/keypress/{RokuConst.COMMANDS[name]}"
                    logging.info(f'Press key {RokuConst.COMMANDS[name]}')
                try:
                    self._post(path)
                except Exception:
                    logging.warning("Can't touch roku server")
            if 'time' in kwargs.keys():
                time.sleep(kwargs['time'])

        try:
            return command
        except Exception:
            time.sleep(0.5)
            return command

    def capture_screen(self, filename):
        """
        Execute the capture screen routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        logging.info("\rStart to capture screen ....\r")
        para = {'param-image-type': 'jpeg'}
        url = "http://%s:8060/capture-screen/secret" % (self.ip)
        r = requests.get(url, json=para)
        response = r.content

        with open(file=filename, mode='wb') as handle:
            handle.write(response)
            handle.close()

    def load_array(self, array_txt):
        """
        Load  array from persistent storage.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        with open(os.getcwd() + f'/config/roku/layout/{array_txt}') as f:
            info = f.readlines()
            arr = [i.strip().split(',') for i in info]
        return arr

    def get_ir_focus(self, filename='dumpsys.xml', secret=False):
        """
        Retrieve the ir focus attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """

        if not secret:
            for _ in range(5):
                url = f'http://{self.ip}:8060/query/focus/secret'
                r = requests.get(url).content.decode('utf-8')
                if 'RoScreenWrapper' in r:
                    self.home(time=1)
                    continue
                if 'SGScreen.RMPScene.ComponentController_0.ViewManager_0.ViewStack_0.MediaView_0.Video_' in r:
                    logging.debug("Don't try to  get index in this way")
                    break
                if 'SGScreen.RMPScene.ComponentController_0.ViewManager_0.ViewStack_0.GridView_0.RenderableNode_0.ZoomRowList_0.RenderableNode_' in r:
                    logging.debug("Don't try to get index in this way")
                    break

                focused = re.findall(r'<text>(.*?)</text>', r)
                if focused:
                    self.ir_current_location = focused[0]
                    return focused[0]
            else:
                return ''
        node_list = []
        for child in self._get_xml_root():
            for child_1 in child.iter():
                if child_1.tag == 'ItemDetailsView':
                    for child_2 in child_1.iter():
                        if child_2.tag == 'Label' and child_2.attrib['name'] == 'title':
                            if child_2.attrib['text']:
                                if '|' in child_2.attrib['text']:
                                    self.ir_current_location = child_2.attrib['text'].split('|')[0].strip()
                                else:
                                    self.ir_current_location = child_2.attrib['text']
                                return self.ir_current_location
                if child_1.tag == 'RenderableNode' and child_1.attrib.get('focused') and child_1.attrib[
                    'focused'] == 'true':
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
                        return self.ir_current_location
                if child_1.tag == 'Button' and child_1.attrib.get('focused') and child_1.attrib['focused'] == 'true':
                    self.ir_current_location = child_1.find('Label').attrib['text']
                    return self.ir_current_location
                if child_1.tag == 'StandardGridItemComponent':
                    if child_1.attrib.get('focused') and child_1.attrib['focused'] == 'true':
                        node_list.append(child_1)
        if node_list:
            self.ir_current_location = node_list[-1].find('LayoutGroup').find('Label').attrib['text']

    def _get_media_process_bar(self, filename='dumpsys.xml'):
        """
        Retrieve the media process bar attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        process_index = '0:0'
        for child in self._get_xml_root():
            for child_1 in child.iter():
                if child_1.tag == 'TrickPlayBar' and not child_1.attrib.get('name'):
                    process_index = child_1.find('Label').attrib['text']
                    logging.info(process_index)
                    logging.info(int(process_index.split(':')[0]) * 60 + int(process_index.split(":")[1]))
                    return int(process_index.split(':')[0]) * 60 + int(process_index.split(":")[1])

    def get_ir_index(self, name, item, fuz_match=False):
        """
        Retrieve the ir index attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """

        target_array = self.get_launcher_element(item)
        for i in target_array:
            for y in i:
                if fuz_match:
                    if name in y:
                        return (target_array.index(i), i.index(y)), len(i)
                else:
                    if name == y:
                        return (target_array.index(i), i.index(y)), len(i)

        logging.debug(f"Can't find such this widget {name}")
        return None, None

    def ir_navigation(self, target, item, secret=False, fuz_match=False):
        """
        Execute the ir navigation routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        logging.info(f'navigation {target}')
        self.get_ir_focus(secret=secret)
        if target in self.ir_current_location:
            target = self.ir_current_location
        current_index, _ = self.get_ir_index(self.ir_current_location, item, fuz_match=fuz_match)
        target_index, list_len = self.get_ir_index(target, item, fuz_match=fuz_match)
        array = self.get_launcher_element(item)
        if current_index and target_index and list_len:
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

        return self.ir_navigation(target, item, secret=secret, fuz_match=fuz_match)

    def ir_enter(self, target, item, secret=False, fuz_match=False):
        """
        Execute the ir enter routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.ir_navigation(target, item, secret=secret, fuz_match=fuz_match)
        self.select(time=2)

    def media_playback(self, target, array):
        """
        Execute the media playback routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.ir_enter(target, array)
        time.sleep(1)
        info = self._get_screen_xml()
        if 'Play from beginning' in info:
            self.down(time=1)
        self.select(time=1)

    def _get_screen_xml(self, filename='dumpsys.xml'):
        """
        Retrieve the screen xml attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        r, focused = '', ''

        for _ in range(5):
            url = f"http://{self.ip}:8060/query/screen/secret"
            r = requests.get(url).content.decode('utf-8')
            if 'Internal error' not in r:
                break
        with open(file=filename, mode='w', encoding='utf-8') as handle:
            handle.write(r)
        return r

    def _get_xml_root(self, filename='dumpsys.xml'):
        """
        Get the xml root attribute from the instance.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self._get_screen_xml(filename)
        tree = ET.parse(filename)
        return tree.getroot()

    def wait_for_element(self, element, timeout=60):
        """
        Execute the wait for element routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        start = time.time()
        while element not in self._get_screen_xml():
            time.sleep(1)
            if time.time() - start > timeout:
                logging.warning(f"Can't loading {element}")
                break

    def get_u_disk_file_distribution(self, filename='dumpsys.xml'):
        """
        Retrieve the u disk file distribution attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """

        node_list, temp = [], []
        current_file = ''
        for child in self._get_xml_root():
            for child_1 in child.iter():
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
        """
        Retrieve the launcher element attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        node_list = []
        current_file = ''
        for child in self._get_xml_root():
            for child_1 in child.iter():
                if child_1.tag == target_element:
                    index = int(child_1.attrib['index'])
                    for child_2 in child_1.iter():
                        if child_2.tag == 'Label' and 'renderPass' not in child_2.attrib:
                            text = child_2.attrib['text']
                            if text and [text] not in node_list:
                                node_list.append([child_2.attrib['text']])
        return node_list

    @classmethod
    def switch_ir(self, status):
        """
        Execute the switch ir routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        ir_command = {
            'on': 'echo 0xD > /sys/class/remote/amremote/protocol',
            'off': 'echo 0x2 > /sys/class/remote/amremote/protocol'
        }
        logging.info(f'Set roku ir {status}')
        pytest.dut.checkoutput(ir_command[status])

    def set_display_size(self, size):
        """
        Set the display size attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
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
        """
        Set the display mode attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
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
        """
        Set the picture mode attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
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
        """
        Set the picture size attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
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
        """
        Set the caption status attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
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
        """
        Set the caption attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
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
        """
        Retrieve the dmesg log attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        with open('dmesg.log', 'a') as f:
            info = pytest.dut.checkoutput('dmesg')
            f.write(info)
        pytest.dut.checkoutput('dmesg -c')

    def get_kernel_log(self, filename='kernel.log'):
        """
        Retrieve the kernel log attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """

        def run_logcast(filename):
            """
            Execute the run logcast routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
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
        info = tl.checkoutput(f'telnet {self.ip} 8080', wildcard=b'onn. Roku TV')
        tl.checkoutput('logcast start')
        time.sleep(1)
        tl.checkoutput('\x03')  # ,wildcard=b'Console')
        time.sleep(1)
        tl.checkoutput('\x1A')
        time.sleep(1)
        tl.checkoutput(f'telnet {self.ip} 8070')
        t = Thread(target=run_logcast, args=(filename,))
        t.daemon = True
        t.start()

    def analyze_logcat(self, re_list, timeout=10):
        """
        Execute the analyze logcat routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        import copy
        target_list = copy.deepcopy(re_list)
        # tl = TelnetTool(self.ip, pytest.dut.wildcard)
        pytest.dut.checkoutput('\x03')
        pytest.dut.checkoutput('\x03')
        pytest.dut.checkoutput('logcat')
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
        """
        Execute the catch err routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        logging.info(f'Start to catch err. Logfile :{filename}')
        with open(filename, 'r') as f:
            info = f.readlines()
        for i in info:
            res = tag_list.findall(i)
            if res:
                logging.warning(res)
        logging.info('Catch done')

    def shutdown(self):
        """
        Execute the shutdown routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        count = 0
        while pytest.light_sensor.check_backlight():
            # shut down the dut before test
            self.send('power', 10)
            if count > 5:
                raise EnvironmentError("Pls check ir control")

    def get_hdmirx_info(self, **kwargs):
        """
        Retrieve the hdmirx info attribute.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        logging.info(f'hdmirx for expect : {kwargs}')

        def match(info):
            """
            Execute the match routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
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
        """
        Execute the enter media player routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
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
        """
        Execute the check udisk routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        return 'Select Media Device' in self._get_screen_xml()

    def enter_bt(self):
        """
        Execute the enter bt routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.ir_enter('Settings', 'LabelListNativeItem')
        self.ir_enter('Remotes & devices', 'ArrayGridItem')
        self.ir_enter('Wireless headphones', 'ArrayGridItem')
        self.select(time=1)

    def enter_wifi(self):
        """
        Execute the enter wifi routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.home(time=1)
        self.ir_enter('Settings', 'LabelListNativeItem')
        self.ir_enter('Network', 'ArrayGridItem')

    def check_conn(self):
        """
        Execute the check conn routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.enter_wifi()
        self.ir_enter('Check connection', 'LabelListItem')
        for _ in range(20):
            if 'Connection check was successful' in self._get_screen_xml():
                return True
            time.sleep(2)
        else:
            return False

    def setup_conn(self):
        """
        Execute the setup conn routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.enter_wifi()
        self.ir_enter('Set up connection', 'LabelListItem')
        if self.get_ir_focus() != 'Wireless':
            self.down()
        logging.info('check wireless')
        assert 'Wireless' == self.get_ir_focus(), "Can't found wireless "
        self.select()
        self.select()
        for _ in range(20):
            time.sleep(1)
            if 'Scan again to see all network' in self._get_screen_xml():
                logging.info('Wi-Fi list catched')
                return
        else:
            assert False, "Can't load wifi scan list"

    def wifi_scan(self, ssid):
        """
        Execute the wifi scan routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """

        def wait():
            """
            Execute the wait routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            for _ in range(20):
                time.sleep(1)
                if 'Looking for wireless networks...' not in self._get_screen_xml():
                    break

        self.setup_conn()
        for i in range(5):
            for info in self.get_launcher_element('ArrayGridItem'):
                logging.info(info[0])
                if ssid in info[0]:
                    logging.info('Find target ssid')
                    return True
            try:
                if i == 0:
                    self.ir_enter('Scan again to see all networks', 'ArrayGridItem', fuz_match=True)
                    wait()
                else:
                    self.ir_enter('Scan again', 'ArrayGridItem', fuz_match=True)
                    wait()
            except TypeError:
                ...
        else:
            logging.info(f"Can't find target ssid {ssid}")
            return False

    @property
    def ser(self):
        """
        Execute the ser routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if self._ser == '': self._ser = serial_tool()
        return self._ser

    def wifi_conn(self, ssid, pwd='', band=5):
        """
        Execute the wifi conn routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        band = 5 if '5G' in ssid else 2
        self.wifi_scan(ssid)
        self.ir_enter(ssid, 'ArrayGridItem', fuz_match=True)
        if 'Recommended network found' in self._get_screen_xml():
            if band == 2:
                self.down()
            self.select()
        if 'Enter the network password for' in self._get_screen_xml():
            if 'Connect' == self.get_ir_focus():
                self.down()
                self.select()
                self.up()
                self.up()
            self.literal(pwd)
            time.sleep(1)
            for _ in range(4):
                self.down()

        self.select()
        for _ in range(20):
            time.sleep(1)
            ip = self.ser.get_ip_address('wlan0')
            if ip:
                pytest.dut = telnet_tool(ip)
                pytest.dut.roku = roku_ctrl(ip)
                self.ip = ip
                logging.info(f'roku ip {self.ip}')
                break
        pytest.dut.roku.home(time=3)
        pytest.dut.roku.home(time=3)
        pytest.dut.roku.home(time=3)
        return True

    def flush_ip(self):
        """
        Execute the flush ip routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        ip = self.ser.get_ip_address('wlan0')
        if ip:
            pytest.dut = telnet_tool(ip)
            pytest.dut.roku = roku_ctrl(ip)
            return True

    def remote(self, button_list, idle=1):
        """
        Execute the remote routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        button_dict = {'h': 'home', 'p': 'play', 's': 'select', 'l': 'left', 'r': 'right', 'd': 'down', 'u': 'up',
                       'b': 'back', 'i': 'info'}
        for i in button_list:
            if i in RokuConst.COMMANDS:
                getattr(self, button_dict[i])(time=idle)
            else:
                logging.info(f'{i} not in button_dict .pls check again')
