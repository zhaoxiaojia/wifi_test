#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2022/11/8 09:58
# @Author  : chao.li
# @Site    :
# @File    : ZTEax5400Config.py
# @Software: PyCharm


from tools.router_tool.RouterControl import RouterTools


class ZTEax5400Config(RouterTools):
    def __init__(self):
        super(ZTEax5400Config, self).__init__()

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

    WIRELESS_MODE_2G_DICT = {
        '802.11 b/g/n': '1',
        '802.11 b/g/n/ax.11b/g/n': '2'
    }

    WIRELESS_MODE_5G_DICT = {
        '802.11 a/n/ac': '1',
        '802.11 a/n/ac/ax.11ac': '2'
    }

    BANDWIDTH_2_DICT = {'20MHz': '1', '40MHz': '2', '20MHz/40MHz': '3'}

    BANDWIDTH_5_DICT = {'20MHz': '1', '20MHz/40MHz': '2', '20MHz/40MHz/80MHz': '3', '20MHz/40MHz/80MHz/160MHz': '4'}

    AUTHENTICATION_METHOD = {
        'OPEN': '1',
        'WPA2(AES)-PSK': '2',
        'WPA-PSK/WPA2-PSK': '3',
        'WPA2-PSK/WPA3-PSK': '4',
    }
