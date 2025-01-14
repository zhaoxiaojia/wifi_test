# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


from dut_control.roku_ctrl import roku_ctrl

roku = roku_ctrl('192.168.0.106')

input('change wifi')
roku = roku_ctrl( '192.168.50.4')

roku.home()