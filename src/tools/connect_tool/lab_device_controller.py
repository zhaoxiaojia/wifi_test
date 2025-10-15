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
        self._last_set_value = None
        self.lda_channels = [1]
        self._last_used_channels = None
        self.tn = None
        if self.model == 'LDA-908V-8':
            lda_config = pytest.config['rf_solution'].get('LDA-908V-8', {})
            try:
                raw_channels = lda_config.get('channels')
                if raw_channels is None and 'ports' in lda_config:
                    logging.warning(
                        'Deprecated configuration key "ports" detected for %s; '
                        'please rename it to "channels"',
                        self.model,
                    )
                    raw_channels = lda_config.get('ports')
                self.lda_channels = self._parse_channels(raw_channels)
            except Exception as exc:
                logging.error('Invalid LDA-908V-8 channels configuration: %s', exc)
                raise
            logging.info(
                'Initialize HTTP attenuator controller %s at %s with channels %s',
                self.model,
                ip,
                self.lda_channels,
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
            self._last_used_channels = list(self.lda_channels)
            for channel in self._last_used_channels:
                params = {'chnl': channel, 'attn': self._last_set_value}
                logging.debug(
                    'Set attenuation for channel %s with params %s',
                    channel,
                    params,
                )
                self._run_curl_command('setup.cgi', params)
        elif self.model == 'RC4DAT-8G-95':
            self.tn.write(f":CHAN:1:2:3:4:SETATT:{value};".encode('ascii') + b'\r\n')
            self.tn.read_some()
        else:
            if not self.tn:
                raise RuntimeError('Telnet connection not initialized')
            logging.info(f"ATT 1 {value};2 {value};3 {value};4 {value};")
            self.tn.write(f"ATT 1 {value};2 {value};3 {value};4 {value};".encode('ascii') + b'\r')
        time.sleep(2)

    def get_rf_current_value(self):
        if self.model == 'LDA-908V-8':
            channels_to_query = self._last_used_channels or self.lda_channels
            results = {}
            for channel in channels_to_query:
                params = {'chnl': channel}
                if self._last_set_value is not None:
                    params['attn'] = self._last_set_value
                logging.debug(
                    'Query attenuation for channel %s with params %s',
                    channel,
                    params,
                )
                response = self._run_curl_command('status.shtm', params)
                if response is None:
                    logging.warning('No response received for channel %s', channel)
                    results[channel] = None
                    continue
                match = re.search(r'(\d+)', response)
                results[channel] = int(match.group(1)) if match else response
            if len(results) == 1:
                return next(iter(results.values()))
            return results
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

    def _run_curl_command(self, endpoint, params):
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

    @staticmethod
    def _parse_channels(raw_channels):
        if raw_channels is None:
            return [1]

        if isinstance(raw_channels, Iterable) and not isinstance(raw_channels, (str, bytes)):
            tokens = []
            for item in raw_channels:
                if item is None:
                    continue
                tokens.extend(re.split(r'[\s,]+', str(item).strip()))
        else:
            tokens = re.split(r'[\s,]+', str(raw_channels).strip())

        channels = set()
        for token in tokens:
            if not token:
                continue
            token_str = str(token).strip()
            if not token_str:
                continue
            if '-' in token_str:
                start_str, end_str = token_str.split('-', 1)
                try:
                    start = int(start_str)
                    end = int(end_str)
                except ValueError as exc:
                    raise ValueError(f'invalid range segment "{token_str}"') from exc
                if start > end:
                    raise ValueError(f'range start greater than end in "{token_str}"')
                for channel in range(start, end + 1):
                    LabDeviceController._validate_port(channel)
                    channels.add(channel)
            else:
                try:
                    channel = int(token_str)
                except ValueError as exc:
                    raise ValueError(f'invalid channel "{token_str}"') from exc
                LabDeviceController._validate_port(channel)
                channels.add(channel)

        if not channels:
            raise ValueError('no valid channels specified')
        return sorted(channels)

    @staticmethod
    def _validate_port(port):
        if port < 1 or port > 8:
            raise ValueError(f'port {port} is out of range 1-8')

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
        # self.tn.read_some().decode('utf-8')
        self.tn.write('gcp'.encode('ascii') + b'\r\n')
        current_angle = int(self.tn.read_some().decode('utf-8'))
        self.angle = int(current_angle)
        logging.info(f'Current angle {self.angle}')
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
