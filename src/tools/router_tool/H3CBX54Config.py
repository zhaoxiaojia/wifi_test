#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2022/10/26 14:13
# @Author  : chao.li
# @Site    :
# @File    : H3CBX54Config.py
# @Software: PyCharm
from src.tools.router_tool.RouterControl import RouterTools


class H3CRouterConfig(RouterTools):
    def __init__(self):
        super(H3CRouterConfig, self).__init__()

    WIRELESS_MODE_2G_DICT = {
        'b-only': '1',
        'g-only': '2',
        'b+g': '3',
        'n-only': '4',
        'b+g+n': '5',
        'b+g+n+ax': '8'
    }

    CHANNEL_2_DICT = {
        'AUTO': '1',
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

    BANDWIDTH_2_LIST = ['自动', '20M', '40M']

    CHANNEL_5_DICT = {
        'AUTO': '1',
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
        '165': '14',
    }

    WIRELESS_MODE_5G_DICT = {
        'a+n': '6',
        'a+n+ac': '7',
        'a+n+ac+ax': '9'
    }

    BANDWIDTH_5_LIST = ['自动', '20M', '40M', '80M', '160M']

    AUTHENTICATION_METHOD_DICT = {
        '不加密': '1',
        'WPA2-PSK': '2',
        'WPA-PSK/WPA2-PSK混合': '3',
        'WPA2-PSK/WPA3-SAE混合': '4'
    }
