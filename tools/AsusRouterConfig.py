#!/usr/bin/env python
# @Time    : 2022/10/18 16:08
# @Author  : chao.li
# @Site    :
# @File    : AsusRouterConfig.py
# @Software: PyCharm

from .RouterConfig import RouterConfig


class AsusRouterConfig(RouterConfig):
    '''
    asus router setting config
    '''

    def __init__(self):
        super(AsusRouterConfig, self).__init__()

    WIRELESS_MODE = ['自动', 'N only', 'AX only', 'N/AC/AX mixed', 'Legacy']
    BANDWIDTH_2_LIST = ['20/40 MHz', '20 MHz', '40 MHz']
    BANDWIDTH_5_LIST = ['20/40/80 MHz', '20 MHz', '40 MHz', '80 MHz']
    WIRELESS_2_MODE = ['自动', 'AX only', 'N only', 'Legacy']
    WIRELESS_5_MODE = ['自动', 'AX only', 'N/AC/AX mixed', 'Legacy']

    AUTHENTICATION_METHOD_DICT = {
        'Open System': '1',
        'WPA2-Personal': '2',
        'WPA3-Personal': '3',
        'WPA/WPA2-Personal': '4',
        'WPA2/WPA3-Personal': '5',
        'WPA2-Enterprise': '6',
        'WPA/WPA2-Enterprise': '7',
    }

    AUTHENTICATION_METHOD_LEGCY_DICT = {
        'Open System': '1',
        'Shared Key': '2',
        'WPA2-Personal': '3',
        'WPA3-Personal': '4',
        'WPA/WPA2-Personal': '5',
        'WPA2/WPA3-Personal': '6',
        'WPA2-Enterprise': '7',
        'WPA/WPA2-Enterprise': '8',
        'Radius with 802.1x': '9',
    }

    PROTECT_FRAME = {
        '停用': 1,
        '非强制启用': 2,
        '强制启用': 3
    }

    WEP_ENCRYPT = {
        'WEP-64bits': '1',
        'WEP-128bits': '2'
    }

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
        '11': '12'
    }
    CHANNEL_5_DICT = {
        'auto': '1',
        '36': '2',
        '40': '3',
        '44': '4',
        '48': '5',
        '52': '6',
        '56': '7',
        '60': '8',
        '64': '9',
        '100': '10',
        '104': '11',
        '108': '12',
        '112': '13',
        '116': '14',
        '120': '15',
        '124': '16',
        '128': '17',
        '132': '18',
        '136': '19',
        '140': '20',
        '144': '21',
        '149': '22',
        '153': '23',
        '157': '24',
        '161': '25',
        '165': '26'
    }
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

class Asus86uConfig(AsusRouterConfig):
    '''
    asus 86u router setting config
    '''

    def __init__(self):
        super(Asus86uConfig, self).__init__()

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


class Asus88uConfig(AsusRouterConfig):
    '''
    asus 88u router setting config
    '''

    def __init__(self):
        super(Asus88uConfig, self).__init__()

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

    BANDWIDTH_5_LIST = ['20/40/80 MHz', '20 MHz', '40 MHz', '80 MHz', '160 MHz']


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

    BANDWIDTH_5_LIST = ['20/40/80 MHz', '20 MHz', '40 MHz', '80 MHz']

    AUTHENTICATION_METHOD_DICT = {
        'Open System': '1',
        'WPA2-Personal': '2',
        'WPA-Auto-Personal': '3',
        'WPA2-Enterprise': '4',
        'WPA-Auto-Enterprise': '5',
    }

    AUTHENTICATION_METHOD_LEGCY_DICT = {
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
