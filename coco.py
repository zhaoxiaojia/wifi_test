# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


import uiautomator2 as u2

d = u2.connect("twilight9de10187801e1c")
print(d.dump_hierarchy())