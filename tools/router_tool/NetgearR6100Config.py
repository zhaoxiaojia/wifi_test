#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2023/1/16
# @Author  : Yu.Zeng
# @Site    :
# @File    : NetgearR6100Config.py
# @Software: PyCharm

from tools.router_tool.RouterConfig import RouterConfig


class NetgearR6100Config(RouterConfig):
    def __init__(self):
        super(NetgearR6100Config, self).__init__()

    CHANNEL_2_DICT = {
        'AUTO': '0',
        '1': '1',
        '2': '2',
        '3': '3',
        '4': '4',
        '5': '5',
        '6': '6',
        '7': '7',
        '8': '8',
        '9': '9',
        '10': '10',
        '11': '11'
    }

    CHANNEL_5_DICT = {
        '36': '36',
        '40': '40',
        '44': '44',
        '48': '48',
        '149': '149',
        '153': '153',
        '157': '157',
        '161': '161'
    }

    WIRELESS_MODE_2_DICT = {
        '54Mbps': '1',
        '145Mbps': '2',
        '300Mbps': '3'
    }

    WIRELESS_MODE_5_DICT = {
        '192Mbps': '7',
        '400Mbps': '8',
        '867Mbps': '9'
    }

    WEP_ENCRYPT_DICT = {
        'wep-64': '5',
        'wep-128': '13'
    }
