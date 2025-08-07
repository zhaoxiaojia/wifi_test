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


def _info(info):
    return 'Default' if info == None else info


def router_str(self):
    return f'{_info(self.band)},{_info(self.ssid)},{_info(self.wireless_mode)},{_info(self.channel)},{_info(self.bandwidth)},{_info(self.authentication)}'


RUN_SETTING_ACTIVITY = 'am start -n com.android.tv.settings/.MainSettings'

fields = ['ap', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'authentication',
          'wpa_passwd', 'test_type', 'protocol_type', 'data_row', 'expected_rate', 'wifi6', 'wep_encrypt', 'wep_passwd',
          'hide_ssid', 'hide_type', 'wpa_encrypt', 'passwd_index', 'protect_frame',
          'smart_connect', 'country_code']

Router = namedtuple('Router', fields, defaults=(None,) * len(fields))
Router.__str__ = router_str
Router.__repr__ = router_str
