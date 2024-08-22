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

coco1 = {"1":{'name':'coco'}}
coco2 = {"2":{'age':18}}


coco2['2'].update({'name':'zues','age':20,'gender':'man'})
print(coco2)