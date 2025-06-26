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

from dataclasses import dataclass
import re
import os
import json
from typing import Literal
from util.mixin import json_mixin, nested_dict

FPGA_CONFIG = {
    'W1': {'mimo': '1X1', '2.4G': '11N', '5G': '11AC'},
    'W1L': {'mimo': '1X1', '2.4G': '11N', '5G': '11AC'},
    'W2': {'mimo': '2X2', '2.4G': '11AX', '5G': '11AX'},
    'W2U': {'mimo': '2X2', '2.4G': '11AX', '5G': '11AX'},
    'W2L': {'mimo': '2X2', '2.4G': '11AX', '5G': '11AX'}
}
dut_wifichip = 'w2_sdio'
wifichip, interface = dut_wifichip.split('_')


@dataclass
class compatibility_router(json_mixin):
    _instances = []

    def set_info(self, ip, port, brand, model, setup):
        info = nested_dict()
        if not re.match(r'\d+\.\d+\.\d+\.', ip):
            raise ValueError("Format error, pls check the ip address")
        if not port.isdigit():
            raise ValueError("Format error, pls check the port")
        info['ip'] = ip
        info['port'] = port
        info['brand'] = brand.upper()
        info['model'] = model.upper()
        for k, v in setup.items():
            info[k] = v
        self._instances.append(info)
        # 直接在 self.__dict__ 中创建嵌套字典

    def __str__(self):
        return self.to_dict()

    def save_expect(self):
        with open(f"{os.getcwd()}/config/compatibility_router.json", 'w') as f:
            json.dump(self._instances, f, indent=4, ensure_ascii=False)


class dut_standard(json_mixin):
    def set_expect(self,
                   band: str,
                   interface: str,
                   mode: str,
                   authentication: str,
                   bandwidth: str,
                   mimo: str,
                   direction: Literal['DL', 'UL'],
                   expect_data: int):
        band, mode, mimo, direction, authentication = map(str.upper, [band, mode, mimo, direction, authentication])

        valid_bands = {'2.4G': ["11N", "11AX"], '5G': ["11AX", "11AC"]}
        valid_bandwidth = {'2.4G': ["20/40MHz", "20MHz", "40MHz"], '5G': ["20/40/80MHz", "20MHz", "40MHz", "80MHz"]}
        valid_mimo = ["1X1", "2X2", "3X3", "4X4"]
        valid_auth = ["WPA3", "WPA2", "WEP", "OPEN SYSTEM"]
        valid_direction = ["UL", "DL"]

        if band not in valid_bands:
            raise ValueError("The band can only be set to '2.4G','5G' ")
        if mode not in valid_bands[band]:
            raise ValueError(f"{band} can only be set to {valid_bands[band]} ")
        if bandwidth not in valid_bandwidth[band]:
            raise ValueError(f"{band} can only be set to {valid_bandwidth[band]} ")
        if mimo not in valid_mimo:
            raise ValueError(f"The mimo can only be set to {valid_mimo}")
        if direction not in valid_direction:
            raise ValueError("The direction can only be set to 'UL','DL'")
        if authentication not in valid_auth:
            raise ValueError("The authenication can only be set to wpa3,wpa2,wep,open system,")
        self[band][interface.upper()][mode][bandwidth][mimo][direction] = expect_data


a = compatibility_router()
a.set_info("192.168.200.4", '2', 'ASUS', 'RT-AX88U Pro',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '7', 'Xiaomi', 'AX3000 RA80',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '1', 'Netgear', 'AX1800 RAX20',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '2', 'TP-LINK', 'TL-XDR6030yizhanban',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '8', 'ASUS', 'RT-AC1900P',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '6', 'Tenda', 'JD12LProxinhaozengqiangban',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '5', 'Tenda', 'BE6LPro',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '3', 'COMFAST', 'CF-WR633AX',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '6', 'TP-LINK', 'TL-7DR7230yizhanban',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '1', 'ZTE', 'ZXSLC SR7410',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '6', 'Huawei', 'AX3Pro WS7206',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '2', 'Huawei', 'XIHE-BE70',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '4', 'ZTE', 'ZXSLC SR6110',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '8', 'MERCURY', 'D126',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '3', 'HONOR', 'X4Pro HLB-600',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '4', 'H3C', 'NX30Pro',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '3', 'ThundeRobot', 'SR5301ZA',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '5', 'Xiaomi', 'BE3600 RD15',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '6', 'Xiaomi', 'R4A',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '7', 'Xiaomi', 'AX3000T RD03',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '7', 'TP-LINK', 'TL-XDR5410yizhanban',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '4', 'H3C', 'Magic NX54',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '1', 'TP-LINK', 'TL-WDR7660qianzhaoyizhanban',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '8', 'ASUS', 'TX-AX6000',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '1', 'ASUS', 'XD4 Pro',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '4', 'NETGEAR', 'RAX50',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '3', 'NETGEAR', 'RAX70',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '8', 'RuiJie', 'RG-EW1300G',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '7', 'RuiJie', 'X60',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '5', 'Netcore', 'LK-DS7587',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '5', 'TP-LINK', 'TL-7DR3630yizhanban',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '2', 'LINKSYS', 'E8450',
           {'2.4G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})
a.set_info("192.168.200.7", '1', 'ARRIS', 'TR4400',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '2', 'ARRIS', 'SBR-AC1200P',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '3', 'ARRIS', 'W21',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '4', 'HUAWEI', 'BE7',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '5', 'BAFFALO', 'WZR-1750DHP',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '6', 'HUAWEI', 'BE3 PRO',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '8', 'ARRIS', 'TG3452',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'}})

a.set_info("192.168.200.8", '1', 'VANTIVA', 'SDX62',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.8", '3', 'PORTAL', '2AFZUSAP102',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.8", '8', 'ARRIS', 'SBR-AC1750',
           {'2.4G': {'mode': '11N', 'authentication': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'authentication': 'wpa2', 'bandwidth': '80MHz'}})

a.save_expect()
dut = dut_standard()
dut.set_expect('2.4G', 'sdio', '11N', 'wpa2', '20MHz', '1x1', 'UL', 42.8)
dut.set_expect('2.4G', 'sdio', '11N', 'wpa2', '20MHz', '1x1', 'DL', 42.8)
dut.set_expect('2.4G', 'sdio', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('2.4G', 'sdio', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('2.4G', 'usb', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('2.4G', 'usb', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('2.4G', 'pcie', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('2.4G', 'pcie', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('2.4G', 'sdio', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('2.4G', 'sdio', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)
dut.set_expect('2.4G', 'usb', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('2.4G', 'usb', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)
dut.set_expect('2.4G', 'pcie', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('2.4G', 'pcie', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)

dut.set_expect('5G', 'sdio', '11AC', 'wpa2', '80MHz', '1x1', 'UL', 209)
dut.set_expect('5G', 'sdio', '11AC', 'wpa2', '80MHz', '1x1', 'DL', 237.5)
dut.set_expect('5G', 'sdio', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 456)
dut.set_expect('5G', 'sdio', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 456)
dut.set_expect('5G', 'usb', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 266)
dut.set_expect('5G', 'usb', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 266)
dut.set_expect('5G', 'pcie', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 570)
dut.set_expect('5G', 'pcie', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 570)
dut.set_expect('5G', 'sdio', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 456)
dut.set_expect('5G', 'sdio', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 456)
dut.set_expect('5G', 'usb', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 266)
dut.set_expect('5G', 'usb', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 266)
dut.set_expect('5G', 'pcie', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 712.5)
dut.set_expect('5G', 'pcie', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 712.5)

with open(f"{os.getcwd()}/config/compatibility_dut.json", 'w', encoding='utf-8') as f:
    json.dump(dut.to_dict(), f, indent=4, ensure_ascii=False)


def handle_expectdata(ip, port, band, dir):
    '''

    Args:
        ip: the ip address of the pdu
        port: the port of router,value ranges from 0-8
        band: the frequency band for Wi-Fi, only can be 2.4G or 5G
        bandwidth: the bandwidth of Wi-Fi
        dir: the direction of the throughput

    Returns:

    '''
    with open(f"{os.getcwd()}/config/compatibility_router.json", 'r') as f:
        router_datas = json.load(f)
    for data in router_datas:
        if data['ip'] == ip and data['port'] == port:
            mode = data[band]['mode']
            bandwidth = data[band]['bandwidth']
            authentication = data[band]['authentication']
            with open(f"{os.getcwd()}/config/compatibility_dut.json", 'r') as f:
                dut_data = json.load(f)
                return dut_data[band][interface][FPGA_CONFIG[wifichip][band]][bandwidth][FPGA_CONFIG[wifichip]['mimo']][
                    dir]

# print(handle_expectdata("192.168.200.6", "7", '2.4G', 'UL'))
