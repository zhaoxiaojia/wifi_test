# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

#
# import uiautomator2 as u2
#
# d = u2.connect("12345678901234")
# print(d.dump_hierarchy())

class coco:
    def __init__(self):
        self.name = 'coco'

    def print_info(self):
        if not hasattr(self,"_field_"):
            print('aaaa')

c = coco()
c.print_info()