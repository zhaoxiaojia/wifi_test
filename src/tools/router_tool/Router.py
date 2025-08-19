#!/usr/bin/env python
# -*- coding: utf-8 -*- 
"""
# File       : Router.py
# Time       ：2023/7/13 10:34
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

from collections import namedtuple
from src.util.constants import RouterConst


def _info(info):
    return 'Default' if info == None else info


def router_str(self):
    return f'{_info(self.band)},{_info(self.ssid)},{_info(self.wireless_mode)},{_info(self.channel)},{_info(self.bandwidth)},{_info(self.security_protocol)}'


RUN_SETTING_ACTIVITY = RouterConst.RUN_SETTING_ACTIVITY
fields = RouterConst.fields
Router = namedtuple('Router', fields, defaults=(None,) * len(fields))
Router.__str__ = router_str
Router.__repr__ = router_str
