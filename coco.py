# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""


class coco:
    @property
    def freq_num(self):
        return self._freq_num

    @freq_num.setter
    def freq_num(self, value):
        self._freq_num = int(value)
        self.channel = int((self._freq_num - 2412) / 5 if self._freq_num < 3000 else (self._freq_num - 5000) / 5)


c = coco()
c.freq_num = '5180'
print(c.channel)
