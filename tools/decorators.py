# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/16 15:11
# @Author  : chao.li
# @File    : decorators.py

import signal
import time
import inspect
import ctypes
import logging
from functools import wraps


def count_down(duration):
    '''
    闹钟-倒计时
    :param duration: 时长 单位秒
    :return:
    '''

    def wrapper(func):
        def inner(*args, **kwargs):
            global res
            start = time.time()
            while time.time() - start < duration:
                res = func(*args, **kwargs)
            return res

        return inner

    return wrapper
def singleton(cls):
    '''
    单例
    :param cls:
    :return:
    '''
    _instance = {}

    def _singleton(*args, **kargs):
        if cls not in _instance:
            _instance[cls] = cls(*args, **kargs)
        return _instance[cls]

    return _singleton


def lazy_proerty(func):
    attr_name = '_lazy_' + func.__name__

    @property
    def _lazy_proerty(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, func(self))
        return getattr(self, attr_name)

    return _lazy_proerty
