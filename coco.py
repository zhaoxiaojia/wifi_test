# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


def step(func):
    def wrapper(*args, **kwargs):
        print('-' * 80)
        print("Step:")
        print(func.__name__)
        print(func.__doc__)
        info = func(*args, **kwargs)
        print('-' * 80)
        return info


    return wrapper


@step
def get_wifi(cmd):
    '''
    get wifi
    Args:
        cmd:

    Returns:

    '''
    print(f'{cmd} get done')


get_wifi('aa')
