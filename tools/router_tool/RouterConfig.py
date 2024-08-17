#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2022/10/26 14:30
# @Author  : chao.li
# @Site    :
# @File    : RouterConfig.py
# @Software: PyCharm


class RouterConfig:
    BAND_LIST = ['2.4 GHz', '5 GHz']


class ConfigError(Exception):
    def __str__(self):
        return 'element error'
