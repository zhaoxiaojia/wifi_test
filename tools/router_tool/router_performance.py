#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: router_performance.py 
@time: 2025/2/14 10:42 
@desc: 
'''
import os
from collections import defaultdict
from dataclasses import dataclass, field
import re
import json

from util.mixin import json_mixin

fpga = {
    'w1': {'mimo': '1x1', '2.4G': '11N', '5G': '11AC'},
    'w1l': {'mimo': '1x1', '2.4G': '11N', '5G': '11AC'},
    'w2': {'mimo': '2x2', '2.4G': '11AX', '5G': '11AX'},
    'w2u': {'mimo': '2x2', '2.4G': '11AX', '5G': '11AX'}
}
dut_fpgs = 'w2'

def nested_defaultdict():
    return defaultdict(nested_defaultdict)


@dataclass
class compatibility_data(json_mixin):
    ip: str
    port: str
    brand: str
    model: str
    data: dict = field(default_factory=nested_defaultdict)

    _instances = []

    def __post_init__(self):
        if not re.match(r'\d+\.\d+\.\d+\.', self.ip):
            raise ValueError("Format error, pls check the ip address")
        if not self.port.isdigit():
            raise ValueError("Format error, pls check the port")
        self.brand = self.brand.upper()
        self.model = self.model.upper()
        compatibility_data._instances.append(self)

    def set_expect(self, band, mode, bandwidth, mimo, direction, expect_data):
        if band.upper() not in ['2.4G', '5G', '6G']:
            raise ValueError("The band can only be set to '2.4G','5G','6G' ")
        if band.upper() == '2.4G':
            if mode.upper() not in ["11N", '11AX']:
                raise ValueError("2.4G can only be set to '11N' or '11AX' ")
            if bandwidth not in ['20/40MHz', '20MHz', '40MHz']:
                raise ValueError("2.4G can only be set to '20/40MHz', '20MHz', '40MHz' ")
        elif band.upper() == '5G':
            if mode.upper() not in ["11AX", "11AC"]:
                raise ValueError("5G can only be set to '11AC' or '11AX' ")
            if bandwidth not in ['20/40/80 MHz', '20MHz', '40MHz', '80MHz']:
                raise ValueError("5G can only be set to '20/40/80MHz', '20MHz', '40MHz', '80MHz' ")
        if mimo not in ['1x1', '2x2', '3x3', '4x4']:
            raise ValueError("The mimo can only be set to '1x1','2x2','3x3','4x4'")
        if direction.upper() not in ['UL', 'DL']:
            raise ValueError("The direction can only be set to 'UL','DL'")
        self.band = band
        self.mode = mode
        self.bandwidth = bandwidth
        self.mimo = mimo
        self.direction = direction
        self.expect_data = expect_data

        self.data[band][mode][bandwidth][mimo][direction] = expect_data

    @classmethod
    def save_expect(cls):
        info = []
        for i in cls._instances:
            print(i.to_dict())
            info.append(i.to_dict())
        with open(f"compatobility_expectdata.json", 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=4, ensure_ascii=False)


a = compatibility_data("192.168.200.1", '1', 'asus', '88u')
a.set_expect('2.4G', '11AX', '40MHz', '2x2', 'UL', 400)
a.set_expect('2.4G', '11AX', '40MHz', '2x2', 'DL', 380)
a.set_expect('5G', '11AX', '40MHz', '2x2', 'UL', 410)
a.set_expect('5G', '11AX', '40MHz', '2x2', 'DL', 375)

b = compatibility_data("192.168.200.2", '1', 'xiaomi', '5000')
b.set_expect('2.4G', '11N', '40MHz', '1x1', 'DL', 110)
b.set_expect('5G', '11AC', '40MHz', '2x2', 'UL', 220)

compatibility_data.save_expect()
