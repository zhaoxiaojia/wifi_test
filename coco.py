# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""
import re
str = "http://192.168.31.1/cgi-bin/luci/web"
print(re.findall("\d+\.\d+\.\d+\.\d+",str)[0])