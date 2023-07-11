import logging
import os
import signal
import time
import re
import pytest
from collections import namedtuple
from typing import Any, Tuple

from .ADB import ADB
from .tools.Asusax88uControl import Asusax88uControl


def router_str(self):
    # info = []
    # for k in dir(self):
    #     if not k.startswith('__') and not k.startswith('_') and k != 'index' and k != 'count':
    #         if getattr(self, k):
    #             info.append(getattr(self, k))
    # return '_'.join(info)
    return f'{self.serial}_{self.band} {self.ssid} {self.wireless_mode} {self.channel} {self.bandwidth} {self.authentication_method}'

RUN_SETTING_ACTIVITY = 'am start -n com.android.tv.settings/.MainSettings'

fields = ['serial', 'band', 'ssid', 'wireless_mode', 'channel', 'bandwidth', 'authentication_method',
          'wpa_passwd', 'test_type', 'protocol_type', 'wep_encrypt', 'wep_passwd',
          'hide_ssid', 'hide_type', 'wpa_encrypt', 'passwd_index', 'protect_frame',
          'smart_connect', 'country_code']
Router = namedtuple('Router', fields, defaults=(None,) * len(fields))
Router.__str__ = router_str
# set install apk not be limited
# if adb.run_shell_cmd('getprop sys.limit.install.app')[1] == "true":
#     adb.run_shell_cmd('setprop sys.limit.install.app false')


# wifi = WifiTestApk(pytest.config_yaml.get_note('device'))
# wifi.root()
# wifi.remount()
# logging.info(f"device {pytest.config_yaml.get_note('device')}")


# accompanying_dut = WifiTestApk()
# accompanying_dut.serialnumber = config_yaml.get_note('accompanying_dut')
# accompanying_dut.root()


wifi_onoff_tag = 'Available networks'
