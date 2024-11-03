#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2022/10/18 16:08
# @Author  : chao.li
# @Site    :
# @File    : AsusRouterConfig.py
# @Software: PyCharm
from typing import List

from tools.router_tool.RouterConfig import RouterConfig


class AsusRouterConfig(RouterConfig):
    '''
    asus router setting config
    '''

    def __init__(self):
        super(AsusRouterConfig, self).__init__()

    WIRELESS_MODE = ['自动', 'N only', 'AX only', 'N/AC/AX mixed', 'Legacy']
    BANDWIDTH_2 = ['20/40 MHz', '20 MHz', '40 MHz']
    BANDWIDTH_5 = ['20/40/80 MHz', '20 MHz', '40 MHz', '80 MHz']
    WIRELESS_2_MODE = ['自动', '11b', '11g', '11n', '11ax', 'Legacy']
    WIRELESS_5_MODE: list[str] = ['自动', '11a', '11ac', '11ax', 'Legacy']

    AUTHENTICATION_METHOD = ['Open System', 'WPA2-Personal', 'WPA3-Personal', 'WPA/WPA2-Personal', 'WPA2/WPA3-Personal',
                             'WPA2-Enterprise', 'WPA/WPA2-Enterprise']

    AUTHENTICATION_METHOD_LEGCY = ['Open System', 'Shared Key', 'WPA2-Personal', 'WPA3-Personal',
                                   'WPA/WPA2-Personal', 'WPA2/WPA3-Personal', 'WPA2-Enterprise',
                                   'WPA/WPA2-Enterprise', 'Radius with 802.1x']

    PROTECT_FRAME = {
        '停用': 1,
        '非强制启用': 2,
        '强制启用': 3
    }

    WEP_ENCRYPT = ['None', 'WEP-64bits', 'WEP-128bits']

    WPA_ENCRYPT = {
        'AES': 1,
        'TKIP+AES': 2
    }

    PASSWD_INDEX_DICT = {
        '1': '1',
        '2': '2',
        '3': '3',
        '4': '4'
    }
    CHANNEL_2 = ['自动', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11']
    CHANNEL_5 = ['自动', '36', '40', '44', '48', '52', '56', '60', '64', '100', '104', '108', '112', '116', '120',
                 '124', '128', '132', '136', '140', '144', '149', '153', '157', '161', '165']
    COUNTRY_CODE = {
        '亚洲': '1',
        '中国 (默认值)': '2',
        '欧洲': '3',
        '韩国': '4',
        '俄罗斯': '5',
        '新加坡': '6',
        '美国': '7',
        '澳大利亚': '8'
    }


class Asusax86uConfig(AsusRouterConfig):
    '''
    asus 86u router setting config
    '''

    def __init__(self):
        super(Asusax86uConfig, self).__init__()

    CHANNEL_2_DICT = {
        'auto': '1',
        '1': '2',
        '2': '3',
        '3': '4',
        '4': '5',
        '5': '6',
        '6': '7',
        '7': '8',
        '8': '9',
        '9': '10',
        '10': '11',
        '11': '12',
        '12': '13',
        '13': '14',
    }


class Asusax88uConfig(AsusRouterConfig):
    '''
    asus 88u router setting config
    '''

    def __init__(self):
        super(Asusax88uConfig, self).__init__()

    CHANNEL_5_DICT = {
        '自动': '1',
        '36': '2',
        '40': '3',
        '44': '4',
        '48': '5',
        '52': '6',
        '56': '7',
        '60': '8',
        '64': '9',
        '149': '10',
        '153': '11',
        '157': '12',
        '161': '13',
    }


class Asus5400Config(AsusRouterConfig):
    def __init__(self):
        super(Asus5400Config, self).__init__()

    BANDWIDTH_5 = ['20/40/80 MHz', '20 MHz', '40 MHz', '80 MHz', '160 MHz']
    WIRELESS_MODE = ['自动', 'N only', 'AX only', 'N/AC mixed', 'Legacy']
    CHANNEL_5_DICT = {
        '自动': '1',
        '36': '2',
        '40': '3',
        '44': '4',
        '48': '5',
        '52': '6',
        '56': '7',
        '60': '8',
        '64': '9',
        '149': '10',
        '153': '11',
        '157': '12',
        '161': '13'
    }


class Asus6700Config(AsusRouterConfig):
    def __init__(self):
        super(Asus5400Config, self).__init__()

    WIRELESS_2_MODE = {
        '自动': '1',
        'N only': '2',
        'Legacy': '3'
    }

    WIRELESS_5_MODE = {
        '自动': '1',
        'N/AC mixed': '2',
        'Legacy': '3'
    }

    BANDWIDTH_5 = ['20/40/80 MHz', '20 MHz', '40 MHz', '80 MHz']

    AUTHENTICATION_METHOD = {
        'Open System': '1',
        'WPA2-Personal': '2',
        'WPA-Auto-Personal': '3',
        'WPA2-Enterprise': '4',
        'WPA-Auto-Enterprise': '5',
    }

    AUTHENTICATION_METHOD_LEGCY = {
        'Open System': '1',
        'Shared Key': '2',
        'WPA-Personal': '3',
        'WPA2-Personal': '4',
        'WPA-Auto-Personal': '5',
        'WPA-Enterprise': '6',
        'WPA2-Enterprise': '7',
        'WPA-Auto-Enterprise': '8',
        'Radius with 802.1x': '9',
    }

    CHANNEL_2_DICT = {
        '自动': '1',
        '1': '2',
        '2': '3',
        '3': '4',
        '4': '5',
        '5': '6',
        '6': '7',
        '7': '8',
        '8': '9',
        '9': '10',
        '10': '11',
        '11': '12',
        '12': '13',
        '13': '14',
    }

    CHANNEL_5_DICT = {
        '自动': '1',
        '36': '2',
        '40': '3',
        '44': '4',
        '48': '5',
        '149': '6',
        '153': '7',
        '157': '8',
        '161': '9',
        '165': '10'
    }
