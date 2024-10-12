# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/19 10:32
# @Author  : chao.li
# @File    : decorators.py

import ctypes
import inspect
import logging
import signal
import threading
import time
from functools import wraps


class MyThead(threading.Thread):
    def __init__(self,target,args=()):
        super(MyThead,self).__init__()
        self.func = target
        self.args = args

    def run(self):
        self.a = self.func(*self.args)

    def get_result(self):
        try:
            return  self.a
        except Exception:
            return None

def set_timeout(limit_time):
    def functions(func):
        # 执行操作
        def run(*params):
            thre_func = MyThead(target=func, args=params)
            # 主线程结束(超出时长),则线程方法结束
            thre_func.setDaemon(True)
            thre_func.start()
            time.sleep(limit_time)
            # 最终返回值(不论线程是否已结束)
            if thre_func.get_result():
                return thre_func.get_result()
            else:
                raise False

        return run

    return functions
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