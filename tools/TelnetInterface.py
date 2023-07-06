#!/usr/bin/env python
# @Time    : 2022/1/10 10:02
# @Author  : chao.li
# @Site    :
# @File    : TelnetInterface.py
# @Software: PyCharm


import telnetlib
import time
import logging
import re


class TelnetInterface():
    def __init__(self, ip):
        self.ip = ip
        try:
            logging.info(f'Try to connect {ip}')
            self.tn = telnetlib.Telnet()
            self.tn.open(self.ip, port=23)
            logging.info('telnet init done')
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
        if self.ip == '192.168.50.10':
            self.tn.write(f"*:CHAN:1:2:3:4:SETATT:{value};".encode('ascii') + b'\r\n')
            self.tn.read_some()
        else:
            self.tn.write(f"ATT 1 {value};2 {value};3 {value};4 {value};".encode('ascii') + b'\r')
        time.sleep(2)

    def get_rf_current_value(self):
        if self.ip == '192.168.50.10':
            self.tn.write("ATT?;".encode('ascii') + b'\r')
            # self.tn.read_some().decode('ascii')
            res = self.tn.read_some().decode('ascii')
            return res.split()[0]
        else:
            self.tn.write("ATT".encode('ascii') + b'\r\n')
            res = self.tn.read_some().decode('utf-8')
            return list(map(int, re.findall(r'\s(\d+);', res)))

    def execute_turntable_cmd(self, type, angle=''):
        if type not in ['gs', 'rt', 'gcp']:
            assert 0, 'type must be gs or tr or gcp'
        if type == 'rt':
            if angle != '':
                self.angle = angle
            else:
                self.angle += 30 * 10
            if angle != self.get_turntanle_current_angle():
                self.tn.write(f"{type} {self.angle % 3600}".encode('ascii') + b'\r\n')
        else:
            self.tn.write(f"{type}".encode('ascii') + b'\r\n')
        self.wait_standyby()
        # self.tn.write(b'exit\r\r')

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
