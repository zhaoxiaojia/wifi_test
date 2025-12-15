#!/usr/bin/env python
# _*_ coding: utf-8 _*_
# @Time    : 2022/11/4 16:10
# @Author  : chao.li
# @Site    :
# @File    : Linksys1200acConfig.py
# @Software: PyCharm

from src.tools.router_tool.RouterControl import RouterTools


class Linksys1200acConfig(RouterTools):
    def __init__(self):
        super(Linksys1200acConfig, self).__init__()

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

    WIRELESS_MODE_2G_DICT = {
        '混合模式': '1',
        '仅使用802.11b/g/n': '2',
        '仅使用802.11b/g': '3',
        '仅使用802.11n': '4',
        '仅使用802.11g': '5',
        '仅使用802.11b': '6'
    }

    WIRELESS_MODE_5G_DICT = {
        '混合模式': '1',
        '仅使用802.11ac': '2',
        '仅使用802.11a/n': '3',
        '仅使用802.11n': '4',
        '仅使用802.11a': '5'
    }

    BANDWIDTH_2_DICT = {'自动': '1', '仅使用20 MHz': '2'}

    BANDWIDTH_5_DICT = {'自动': '1', '仅使用20 MHz': '2', '40 MHz': '3', '80 MHz': '4'}

    AUTHENTICATION_METHOD_DICT = {
        '无': '1',
        'WEP': '2',
        'WPA2个人': '3',
        'WPA2企业': '4',
        'WPA2/WPA混合个人模式': '5',
        'WPA2/WPA混合企业模式': '6'
    }

    WEP_ENCRYPT = {
        '40/64位（10个十六进制数字）': '1',
        '104/128位（26个十六进制数字）': '2'
    }
