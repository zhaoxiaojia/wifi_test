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


def router_str(self):
    return f'{self.serial}_{self.band} {self.ssid} {self.wireless_mode} {self.channel} {self.bandwidth} {self.authentication_method}'


RUN_SETTING_ACTIVITY = 'am start -n com.android.tv.settings/.MainSettings'

fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'authentication_method',
          'wpa_passwd', 'test_type', 'protocol_type', 'data_row', 'wep_encrypt', 'wep_passwd',
          'hide_ssid', 'hide_type', 'wpa_encrypt', 'passwd_index', 'protect_frame',
          'smart_connect', 'country_code']
Router = namedtuple('Router', fields, defaults=(None,) * len(fields))
Router.__str__ = router_str
