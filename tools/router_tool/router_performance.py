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
from typing import Literal
from util.mixin import json_mixin

fpga = {
    'w1': {'mimo': '1x1', '2.4G': '11N', '5G': '11AC'},
    'w1l': {'mimo': '1x1', '2.4G': '11N', '5G': '11AC'},
    'w2': {'mimo': '2x2', '2.4G': '11AX', '5G': '11AX'},
    'w2u': {'mimo': '2x2', '2.4G': '11AX', '5G': '11AX'}
}
dut_wifichip = 'w2_sdio'
wifichip, interface = dut_wifichip.split('_')


def nested_dict():
    """递归创建嵌套字典"""
    return defaultdict(nested_dict)


@dataclass
class compatibility_data(json_mixin):
    ip: str
    port: str
    brand: str
    model: str
    _instances = []

    def __post_init__(self):
        if not re.match(r'\d+\.\d+\.\d+\.', self.ip):
            raise ValueError("Format error, pls check the ip address")
        if not self.port.isdigit():
            raise ValueError("Format error, pls check the port")
        self.brand = self.brand.upper()
        self.model = self.model.upper()
        # 直接在 self.__dict__ 中创建嵌套字典
        compatibility_data._instances.append(self)

    def set_expect(self,
                   band: str,
                   interface: str,
                   mode: str,
                   authentication: str,
                   bandwidth: str,
                   mimo: str,
                   direction: Literal['ul', 'dl', 'DL', 'UL'],
                   expect_data: int):
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
        if authentication.upper() not in ['WPA3', 'WPA2', 'WEP', 'OPEN SYSTEM']:
            raise ValueError("The authenication can only be set to wpa3,wpa2,wep,open system,")

        self[band][interface][mode][bandwidth][mimo][direction] = expect_data

    def __getitem__(self, key):
        """确保 self.__dict__['_storage'] 可以被嵌套访问"""
        if key not in self.__dict__:
            self.__dict__[key] = nested_dict()
        return self.__dict__[key]

    def __setitem__(self, key, value):
        """支持嵌套赋值"""
        self.__dict__[key] = value

    @classmethod
    def save_expect(cls):
        info = []
        for i in cls._instances:
            info.append(i.to_dict())
        # with open(f"{os.getcwd()}/config/compatobility_expectdata.json", 'w', encoding='utf-8') as f:
        with open(f"compatobility_expectdata.json", 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=4, ensure_ascii=False)


a = compatibility_data("192.168.200.1", '1', 'asus', '88u')
a.set_expect('2.4G', 'sdio', '11AX', 'wpa3', '40MHz', '2x2', 'UL', 400)
a.set_expect('2.4G', 'usb', '11AX', 'wpa3', '40MHz', '2x2', 'DL', 380)
a.set_expect('5G', 'pcie', '11AX', 'wpa3', '40MHz', '2x2', 'UL', 410)
a.set_expect('5G', 'sdio', '11AX', 'wpa3', '40MHz', '2x2', 'DL', 375)

b = compatibility_data("192.168.200.2", '1', 'xiaomi', '5000')
b.set_expect('2.4G', 'sdio', '11N', 'wpa3', '40MHz', '1x1', 'DL', 110)
b.set_expect('5G', 'sdio', '11AX', 'wpa3', '40MHz', '2x2', 'UL', 220)

compatibility_data.save_expect()


def handle_expectdata(ip, port, band, bandwidth, dir):
    '''

    Args:
        ip: the ip address of the pdu
        port: the port of router,value ranges from 0-8
        band: the frequency band for Wi-Fi, only can be 2.4G or 5G
        bandwidth: the bandwidth of Wi-Fi
        dir: the direction of the throughput

    Returns:

    '''
    # with open(f"{os.getcwd()}/config/compatobility_expectdata.json", 'r') as f:
    with open(f"compatobility_expectdata.json", 'r') as f:
        router_datas = json.load(f)
    for data in router_datas:
        if data['ip'] == ip and data['port'] == port:
            return data[band][interface][fpga[wifichip][band]][bandwidth][fpga[wifichip]['mimo']][dir]


print(handle_expectdata("192.168.200.1", "1", "2.4G", "40MHz", 'UL'))
