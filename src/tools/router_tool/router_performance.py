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
from src.util.mixin import json_mixin, nested_dict
from src.util.constants import RouterConst

wifichip, interface = RouterConst.dut_wifichip.split('_')


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
    def set_expect(self, *args):
        """
        Supported signatures:
        1) set_expect(chip, band, interface, mode, authentication, bandwidth, mimo, direction, expect_data)
        2) set_expect(band, interface, mode, authentication, bandwidth, mimo, direction, expect_data)
           -> falls back to chip='COMMON' for backward compatibility.
        """
        if len(args) == 9:
            chip, band, interface, mode, authentication, bandwidth, mimo, direction, expect_data = args
        elif len(args) == 8:
            chip = 'COMMON'
            band, interface, mode, authentication, bandwidth, mimo, direction, expect_data = args
        else:
            raise TypeError("set_expect() expects 8 or 9 positional arguments.")

        # normalize keys
        chip = str(chip).upper()
        band = str(band).upper()
        interface = str(interface).upper()
        mode = str(mode).upper()
        authentication = str(authentication).upper()
        bandwidth_key = str(bandwidth).upper()
        mimo_key = str(mimo).upper()
        direction_key = str(direction).upper()

        # validation (kept conservative; adjust if needed)
        valid_bands = {'2.4G': ["11N", "11AX"], '5G': ["11AX", "11AC"]}
        valid_bandwidth = {'2.4G': ["20/40MHZ", "20MHZ", "40MHZ"],
                           '5G': ["20/40/80MHZ", "20MHZ", "40MHZ", "80MHZ"]}
        valid_mimo = ["1X1", "2X2", "3X3", "4X4"]
        valid_auth = ["WPA3", "WPA2", "WEP", "OPEN SYSTEM"]
        valid_direction = ["UL", "DL"]

        if band not in valid_bands:
            raise ValueError("band must be one of: 2.4G, 5G")
        if mode not in valid_bands[band]:
            raise ValueError(f"mode for {band} must be one of: {valid_bands[band]}")
        if bandwidth_key not in valid_bandwidth[band]:
            raise ValueError(f"bandwidth for {band} must be one of: {valid_bandwidth[band]}")
        if mimo_key not in valid_mimo:
            raise ValueError(f"mimo must be one of: {valid_mimo}")
        if direction_key not in valid_direction:
            raise ValueError("direction must be UL or DL")
        if authentication not in valid_auth:
            raise ValueError("authentication must be one of: WPA3, WPA2, WEP, OPEN SYSTEM")

        # new structure (chip dimension + authentication dimension)
        self[chip][band][interface][mode][authentication][bandwidth_key][mimo_key][direction_key] = expect_data


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

a.set_info("192.168.200.7", '7', 'HUAWEI', 'BE3 PRO',
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
# w1
dut.set_expect('W1', '2.4G', 'sdio', '11N', 'wpa2', '20MHz', '1x1', 'UL', 42.8)
dut.set_expect('W1', '2.4G', 'sdio', '11N', 'wpa2', '20MHz', '1x1', 'DL', 42.8)
dut.set_expect('W1', '2.4G', 'sdio', '11N', 'wpa2', '40MHz', '1x1', 'UL', 85.5)
dut.set_expect('W1', '2.4G', 'sdio', '11N', 'wpa2', '40MHz', '1x1', 'DL', 85.5)
dut.set_expect('W1', '5G', 'sdio', '11AC', 'wpa2', '80MHz', '1x1', 'UL', 209)
dut.set_expect('W1', '5G', 'sdio', '11AC', 'wpa2', '80MHz', '1x1', 'DL', 237.5)

# w2
dut.set_expect('W2', '2.4G', 'sdio', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('W2', '2.4G', 'sdio', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('W2', '2.4G', 'usb', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('W2', '2.4G', 'usb', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('W2', '2.4G', 'pcie', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('W2', '2.4G', 'pcie', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('W2', '2.4G', 'sdio', '11N', 'wpa2', '40MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2', '2.4G', 'sdio', '11N', 'wpa2', '40MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2', '2.4G', 'usb', '11N', 'wpa2', '40MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2', '2.4G', 'usb', '11N', 'wpa2', '40MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2', '2.4G', 'pcie', '11N', 'wpa2', '40MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2', '2.4G', 'pcie', '11N', 'wpa2', '40MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2', '2.4G', 'sdio', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2', '2.4G', 'sdio', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2', '2.4G', 'usb', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2', '2.4G', 'usb', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2', '2.4G', 'pcie', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2', '2.4G', 'pcie', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2', '2.4G', 'sdio', '11AX', 'wpa2', '40MHz', '2x2', 'UL', 325)
dut.set_expect('W2', '2.4G', 'sdio', '11AX', 'wpa2', '40MHz', '2x2', 'DL', 325)
dut.set_expect('W2', '2.4G', 'usb', '11AX', 'wpa2', '40MHz', '2x2', 'UL', 239)
dut.set_expect('W2', '2.4G', 'usb', '11AX', 'wpa2', '40MHz', '2x2', 'DL', 239)
dut.set_expect('W2', '2.4G', 'pcie', '11AX', 'wpa2', '40MHz', '2x2', 'UL', 325)
dut.set_expect('W2', '2.4G', 'pcie', '11AX', 'wpa2', '40MHz', '2x2', 'DL', 325)
dut.set_expect('W2', '2.4G', 'sdio', '11AC', 'wpa2', '20MHz', '2x2', 'UL', 111.2)
dut.set_expect('W2', '2.4G', 'sdio', '11AC', 'wpa2', '20MHz', '2x2', 'DL', 111.2)
dut.set_expect('W2', '2.4G', 'usb', '11AC', 'wpa2', '20MHz', '2x2', 'UL', 111.2)
dut.set_expect('W2', '2.4G', 'usb', '11AC', 'wpa2', '20MHz', '2x2', 'DL', 111.2)
dut.set_expect('W2', '2.4G', 'pcie', '11AC', 'wpa2', '20MHz', '2x2', 'UL', 111.2)
dut.set_expect('W2', '2.4G', 'pcie', '11AC', 'wpa2', '20MHz', '2x2', 'DL', 111.2)
dut.set_expect('W2', '2.4G', 'sdio', '11AC', 'wpa2', '40MHz', '2x2', 'UL', 239.4)
dut.set_expect('W2', '2.4G', 'sdio', '11AC', 'wpa2', '40MHz', '2x2', 'DL', 239.4)
dut.set_expect('W2', '2.4G', 'usb', '11AC', 'wpa2', '40MHz', '2x2', 'UL', 239.4)
dut.set_expect('W2', '2.4G', 'usb', '11AC', 'wpa2', '40MHz', '2x2', 'DL', 239.4)
dut.set_expect('W2', '2.4G', 'pcie', '11AC', 'wpa2', '40MHz', '2x2', 'UL', 239.4)
dut.set_expect('W2', '2.4G', 'pcie', '11AC', 'wpa2', '40MHz', '2x2', 'DL', 239.4)
dut.set_expect('W2', '5G', 'sdio', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 456)
dut.set_expect('W2', '5G', 'sdio', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 456)
dut.set_expect('W2', '5G', 'usb', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 266)
dut.set_expect('W2', '5G', 'usb', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 266)
dut.set_expect('W2', '5G', 'pcie', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 570)
dut.set_expect('W2', '5G', 'pcie', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 570)
dut.set_expect('W2', '5G', 'sdio', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 456)
dut.set_expect('W2', '5G', 'sdio', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 456)
dut.set_expect('W2', '5G', 'usb', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 266)
dut.set_expect('W2', '5G', 'usb', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 266)
dut.set_expect('W2', '5G', 'pcie', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 712.5)
dut.set_expect('W2', '5G', 'pcie', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 712.5)

# w2l
dut.set_expect('W2L', '2.4G', 'sdio', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('W2L', '2.4G', 'sdio', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('W2L', '2.4G', 'usb', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('W2L', '2.4G', 'usb', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('W2L', '2.4G', 'sdio', '11N', 'wpa2', '40MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2L', '2.4G', 'sdio', '11N', 'wpa2', '40MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2L', '2.4G', 'usb', '11N', 'wpa2', '40MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2L', '2.4G', 'usb', '11N', 'wpa2', '40MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2L', '2.4G', 'sdio', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2L', '2.4G', 'sdio', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2L', '2.4G', 'usb', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2L', '2.4G', 'usb', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2L', '2.4G', 'sdio', '11AX', 'wpa2', '40MHz', '2x2', 'UL', 325)
dut.set_expect('W2L', '2.4G', 'sdio', '11AX', 'wpa2', '40MHz', '2x2', 'DL', 325)
dut.set_expect('W2L', '2.4G', 'usb', '11AX', 'wpa2', '40MHz', '2x2', 'UL', 239)
dut.set_expect('W2L', '2.4G', 'usb', '11AX', 'wpa2', '40MHz', '2x2', 'DL', 239)
dut.set_expect('W2L', '2.4G', 'sdio', '11AC', 'wpa2', '20MHz', '2x2', 'UL', 111.2)
dut.set_expect('W2L', '2.4G', 'sdio', '11AC', 'wpa2', '20MHz', '2x2', 'DL', 111.2)
dut.set_expect('W2L', '2.4G', 'usb', '11AC', 'wpa2', '20MHz', '2x2', 'UL', 111.2)
dut.set_expect('W2L', '2.4G', 'usb', '11AC', 'wpa2', '20MHz', '2x2', 'DL', 111.2)
dut.set_expect('W2L', '2.4G', 'sdio', '11AC', 'wpa2', '40MHz', '2x2', 'UL', 239.4)
dut.set_expect('W2L', '2.4G', 'sdio', '11AC', 'wpa2', '40MHz', '2x2', 'DL', 239.4)
dut.set_expect('W2L', '2.4G', 'usb', '11AC', 'wpa2', '40MHz', '2x2', 'UL', 239.4)
dut.set_expect('W2L', '2.4G', 'usb', '11AC', 'wpa2', '40MHz', '2x2', 'DL', 239.4)
dut.set_expect('W2L', '5G', 'sdio', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 456)
dut.set_expect('W2L', '5G', 'sdio', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 456)
dut.set_expect('W2L', '5G', 'usb', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 266)
dut.set_expect('W2L', '5G', 'usb', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 266)
dut.set_expect('W2L', '5G', 'sdio', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 475)
dut.set_expect('W2L', '5G', 'sdio', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 503.5)
dut.set_expect('W2L', '5G', 'usb', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 266)
dut.set_expect('W2L', '5G', 'usb', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 266)

with open(f"{os.getcwd()}/config/compatibility_dut.json", 'w', encoding='utf-8') as f:
    json.dump(dut.to_dict(), f, indent=4, ensure_ascii=False)


def handle_expectdata(router_info, band, direction, chip_info=None):
    """
    根据路由器信息和芯片方案获取预期吞吐率

    Args:
        router_info: 路由器信息字典，至少包含 band 对应的 mode、authentication、bandwidth
        band: '2.4G' or '5G'
        direction: 'UL' or 'DL'
        chip_info: 如 'w2_sdio'
    Returns:
        float expected throughput
    """
    if chip_info is None:
        chip_info = RouterConst.dut_wifichip

    mode = str(router_info[band]['mode']).upper()
    bandwidth = str(router_info[band]['bandwidth']).upper()
    authentication = 'WPA2'

    chip, interface = chip_info.split('_')
    chip_key = chip.upper()
    if chip_key in ('W1', 'W1U'):
        chip_key = 'W1'
    elif chip_key in ('W2', 'W2U'):
        chip_key = 'W2'
    elif chip_key == 'W2L':
        chip_key = 'W2L'
    interface_key = interface.upper()
    mimo_key = RouterConst.FPGA_CONFIG[chip_key]['mimo'].upper()

    with open(f"{os.getcwd()}/config/compatibility_dut.json", 'r', encoding='utf-8') as f2:
        dut_data = json.load(f2)

    for ck in (chip_key, 'COMMON'):
        try:
            return dut_data[ck][band.upper()][interface_key][mode][authentication][bandwidth][mimo_key][
                direction.upper()]
        except KeyError:
            continue

    raise KeyError(
        f"Missing expected data: chip={chip_key} or COMMON, band={band}, interface={interface_key}, "
        f"mode={mode}, auth={authentication}, bw={bandwidth}, mimo={mimo_key}, dir={direction.upper()}"
    )
