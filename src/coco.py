# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

with open('../README.md', 'rb') as f:
    content = f.read().decode('gbk')  # 先按GBK解码
with open('../README.md', 'w', encoding='utf-8') as f:
    f.write(content)  # 再写入UTF-8