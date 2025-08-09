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

def _async_raise(tid, exctype):
    """raise exctype in the thread with id tid"""
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid), ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res > 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid), 0)
        raise SystemError("PyThreadState_SetAsyncExc failed")

class MyThead(threading.Thread):
    def __init__(self, target, args=()):
        super().__init__()
        self.func = target
        self.args = args
        self.result = None

    def run(self):
        self.result = self.func(*self.args)

    def stop(self):
        if self.ident:
            _async_raise(self.ident, SystemExit)

    def get_result(self):
        return self.result


def set_timeout(limit_time):
    def functions(func):
        @wraps(func)
        def run(*params):
            thre_func = MyThead(target=func, args=params)
            thre_func.daemon = True
            thre_func.start()
            thre_func.join(limit_time)
            if thre_func.is_alive():
                thre_func.stop()
                raise TimeoutError(f"{func.__name__} timeout")
            return thre_func.get_result()

        return run

    return functions


def count_down(duration):
    '''
    闹钟-倒计时
    :param duration: 时长 单位秒
    :return:
    '''

    def wrapper(func):
        res = None
        def inner(*args, **kwargs):
            nonlocal res
            start = time.time()
            while time.time() - start < duration:
                try:
                    res = func(*args, **kwargs)
                except Exception as err:
                    logging.exception("count_down wrapped function raised an exception: %s", err)
                    break
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
