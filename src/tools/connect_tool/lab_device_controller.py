#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2022/1/10 10:02
# @Author  : chao.li
# @Site    :
# @File    : lab_device_controller.py
# @Software: PyCharm


import logging
import re
import time
import telnetlib
from collections.abc import Iterable
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest



class LabDeviceController:
    def __init__(self, ip):
        self.ip = ip
        self.model = pytest.config['rf_solution']['model']
        self._channels = [1]
        self._last_set_value = None
        self.tn = None
        if self.model == 'LDA-908V-8':
            self._channels = self._load_lda_channels()
            logging.info(
                'Initialize HTTP attenuator controller %s at %s (channels=%s)',
                self.model,
                ip,
                ','.join(map(str, self._channels)),
            )
            return
        try:
            logging.info(f'Try to connect {ip}')
            self.tn = telnetlib.Telnet()
            self.tn.open(self.ip, port=23)
            logging.info('*' * 80)
            logging.info(f'* ip   : {ip}')
            logging.info(f'* port: 23')
            logging.info('*' * 80)
            # print('telnet init done')

        except Exception as f:
            logging.info(f)
            return None

    def turn_table_init(self):
        # self.tn.write('gcp'.encode('ascii') + b'\r\n')
        # current_angle = int(self.tn.read_some().decode('utf-8'))
        self.angle = 0
        logging.info('current_angle', self.angle)

    def execute_rf_cmd(self, value):
        if isinstance(value, int):
            value = str(value)
        if int(value) < 0 or int(value) > 110:
            assert 0, 'value must be in range 1-110'
        logging.info(f'Set rf value to {value}')
        if self.model == 'LDA-908V-8':
            self._last_set_value = int(value)
            for channel in self._channels:
                params = {'chnl': channel, 'attn': self._last_set_value}
                self._send_http_request('setup.cgi', params)
        elif self.model == 'RC4DAT-8G-95':
            self.tn.write(f":CHAN:1:2:3:4:SETATT:{value};".encode('ascii') + b'\r\n')
            self.tn.read_some()
        else:
            if not self.tn:
                raise RuntimeError('Telnet connection not initialized')
            self.tn.write(f"ATT 1 {value};2 {value};3 {value};4 {value};".encode('ascii') + b'\r')
        time.sleep(2)

    def get_rf_current_value(self):
        if self.model == 'LDA-908V-8':
            channel = self._channels[0]
            params = {'chnl': channel}
            if self._last_set_value is not None:
                params['attn'] = self._last_set_value
            response = self._send_http_request('status.shtm', params)
            if response is None:
                return None
            match = re.search(r'(\d+)', response)
            return int(match.group(1)) if match else response
        if self.model == 'RC4DAT-8G-95':
            self.tn.write("ATT?;".encode('ascii') + b'\r')
            # self.tn.read_some().decode('ascii')
            res = self.tn.read_some().decode('ascii')
            return res.split()[0]
        else:
            if not self.tn:
                raise RuntimeError('Telnet connection not initialized')
            self.tn.write("ATT".encode('ascii') + b'\r\n')
            res = self.tn.read_some().decode('utf-8')
            return list(map(int, re.findall(r'\s(\d+);', res)))

    def _send_http_request(self, endpoint, params):
        url = f"http://{self.ip}/{endpoint}"
        query = urlencode(params)
        full_url = f"{url}?{query}" if query else url
        logging.info('Send HTTP request to %s', full_url)
        try:
            with urlopen(full_url, timeout=5) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
                logging.debug('Response from %s: %s', endpoint, content)
                return content
        except URLError as exc:
            logging.error('Failed to request %s: %s', full_url, exc)
            raise

    def _load_lda_channels(self):
        cfg = pytest.config.get('rf_solution', {})
        model_cfg = cfg.get(self.model, {}) if isinstance(cfg, dict) else {}
        raw = model_cfg.get('channels')
        try:
            channels = self._parse_channel_values(raw)
        except ValueError as exc:
            raise ValueError(
                'Invalid rf_solution.LDA-908V-8.channels configuration'
            ) from exc
        if not channels:
            raise ValueError('rf_solution.LDA-908V-8.channels must contain at least one valid channel')
        return channels

    @staticmethod
    def _parse_channel_values(raw):
        if raw is None:
            return [1]
        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                return [1]
            items = [item for item in re.split(r'[\s,]+', raw) if item]
        elif isinstance(raw, Iterable) and not isinstance(raw, (bytes, bytearray)):
            items = list(raw)
        else:
            raise ValueError(f'Invalid channel configuration type: {type(raw)!r}')

        channels = []
        for item in items:
            if isinstance(item, str):
                item = item.strip()
            if item == '' or item is None:
                continue
            try:
                channel = int(item)
            except (TypeError, ValueError) as exc:
                raise ValueError(f'Invalid channel value: {item!r}') from exc
            if not 1 <= channel <= 8:
                raise ValueError(f'Channel {channel} out of range (1-8)')
            if channel not in channels:
                channels.append(channel)
        if not channels:
            return [1]
        return channels

    def execute_turntable_cmd(self, type, angle=''):
        if type not in ['gs', 'rt', 'gcp']:
            assert 0, 'type must be gs or tr or gcp'
        if type == 'rt':
            if angle == '':
                angle += self.get_turntanle_current_angle() + 30 * 10
            if angle != self.get_turntanle_current_angle():
                self.tn.write(f"{type} {angle % 3600}".encode('ascii') + b'\r\n')
        else:
            self.tn.write(f"{type}".encode('ascii') + b'\r\n')
        self.wait_standyby()

    def set_turntable_zero(self):
        self.tn.write('rt 0'.encode('ascii') + b'\r\n')
        time.sleep(2)
        logging.info('try to wait ')
        self.wait_standyby()

    def wait_standyby(self):
        start = time.time()
        while time.time() - start < 60:
            self.tn.write('gs'.encode('ascii') + b'\r\n')
            log = self.tn.read_some().decode('utf-8').strip()
            time.sleep(1)
            if 'standby' in log:
                self.tn.write('gcp'.encode('ascii') + b'\r\n')
                self.tn.read_some().decode('utf-8')
                return
        assert 0, 'wait for standby over time'

    def get_turntanle_current_angle(self):
        logging.info('Try to get status')
        # self.tn.read_some().decode('utf-8')
        self.tn.write('gcp'.encode('ascii') + b'\r\n')
        current_angle = int(self.tn.read_some().decode('utf-8'))
        self.angle = int(current_angle)
        return self.angle

# tn = TelnetInterface("192.168.50.200")
# tn.turn_table_init()
# tn.set_turntable_zero()
# tn.execute_turntable_cmd('rt',angle=900)
# if not hasattr(tn, "tn"):
#     print('Telnet 无法实例')


# tn.execute_turntable_cmd('rt')
# tn.execute_turntable_cmd('rt')

# print('Try to rt 100')
# tn.tn.write('rt 3600'.encode('ascii') + b'\r\n')
#
#
# tn.get_turntanle_current_angle()

# current = 0
# rf = TelnetInterface('192.168.50.19')
#
# rf.execute_rf_cmd(80)
#
# print(rf.get_rf_current_value())

# for i in range(20):
#     rf.execute_rf_cmd(current)
#     current += 3
#     print(current)
#     time.sleep(30)

# rf = TelnetInterface("192.168.50.10")
# rf.tn.read_some()
# rf.execute_rf_cmd('95')
# print(rf.get_rf_current_value())
# rf.execute_rf_cmd('35')
# print(rf.get_rf_current_value())
