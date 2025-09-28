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
    if info is None:
        return 'Default'

    cleaned = str(info).strip()
    if not cleaned or cleaned.lower() in {"none", "null"}:
        return 'Default'

    return cleaned


def router_str(self):
    parts = (
        _info(self.band),
        _info(self.ssid),
        _info(self.wireless_mode),
        _info(self.channel),
        _info(self.bandwidth),
        _info(self.security_mode),
    )
    return ''.join(parts)


RUN_SETTING_ACTIVITY = RouterConst.RUN_SETTING_ACTIVITY
fields = RouterConst.fields
Router = namedtuple('Router', fields, defaults=(None,) * len(fields))
Router.__str__ = router_str
Router.__repr__ = router_str
