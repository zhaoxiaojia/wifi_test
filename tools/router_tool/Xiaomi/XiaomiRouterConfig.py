#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2022/11/3 09:40
# @Author  : chao.li
# @Site    :
# @File    : XiaomiRouterConfig.py
# @Software: PyCharm

from tools.router_tool.RouterConfig import RouterConfig


class XiaomiRouterConfig(RouterConfig):
    def __init__(self):
        super(XiaomiRouterConfig, self).__init__()

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
        '165': '14'
    }

    AUTHENTICATION_METHOD_DICT = {
        '超强加密(WPA3个人版)': '1',
        '强混合加密(WPA3/WPA2个人版)': '2',
        '强加密(WPA2个人版)': '3',
        '混合加密(WPA/WPA2个人版)': '4',
        '无加密(允许所有人连接)': '5'
    }

    BANDWIDTH_5_LIST = {
        '160/80/40/20MHz': '1',
        '20MHz': '2',
        '40MHz': '3',
        '80MHz': '4'
    }

    BANDWIDTH_2_LIST = {
        '40/20MHz': '1',
        '20MHz': '2',
        '40MHz': '3'
    }


class Xiaomiax3000Config(XiaomiRouterConfig):
    def __init__(self):
        super().__init__()
