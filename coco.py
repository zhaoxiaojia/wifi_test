# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""
import time
import re
info = '[SUM]  0.0-51.0 sec   969 MBytes   271 Mbits/sec'

if re.findall(r'\[SUM\]  0.0-[3|4|5]\d',info,re.S):
    print('find it')