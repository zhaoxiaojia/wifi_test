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


def handle_files(a,b,c,d):
    arrays = [arr for arr in [a, b, c, d] if arr]

    # 使用itertools.product遍历组合
    for combination in itertools.product(*arrays):
        print(combination)


handle_files(['a','b','c','d'],[1,2,3],[],['coco','zues'])
'''
('a', 1, 'coco')
('a', 1, 'zues')
('a', 2, 'coco')
('a', 2, 'zues')
('a', 3, 'coco')
('a', 3, 'zues')
('b', 1, 'coco')
('b', 1, 'zues')
('b', 2, 'coco')
('b', 2, 'zues')
('b', 3, 'coco')
('b', 3, 'zues')
('c', 1, 'coco')
('c', 1, 'zues')
('c', 2, 'coco')
('c', 2, 'zues')
('c', 3, 'coco')
('c', 3, 'zues')
('d', 1, 'coco')
('d', 1, 'zues')
('d', 2, 'coco')
('d', 2, 'zues')
('d', 3, 'coco')
('d', 3, 'zues')

'''