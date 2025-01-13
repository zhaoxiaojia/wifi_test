# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


from roku import Roku

# roku = Roku('192.168.0.250')
# roku.literal(' ')

a = 'AP-002-2.4G'
b = 'AP-002-2.4G   (-23)'

print(a in b)