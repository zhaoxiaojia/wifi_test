# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""
import itertools

params = list(itertools.product(['xiaomi3000', 'asus88u'], ['tx', 'rx']))
ids = [f"Test_{i[0]} {i[1][0]}" for i in enumerate(params)]
print(ids)