# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/11/6 10:36
# @Author  : chao.li
# @File    : __init__.py.py
# @Project : wifi_test
# @Software: PyCharm



import logging
import os
import time

import pytest

from dut_control.roku_ctrl import roku_ctrl
from tools.pil_tool import PilTool
from tools.yamlTool import yamlTool

pytest.dut.roku = roku_ctrl()
# pytest.executer.execute_cmd('echo 6 > /proc/sys/kernel/printk')

# info = pytest.executer.checkoutput('[ -e /nvram/debug_overlay/etc/autostart ] && echo "yes" || echo "no"')
# pytest.executer.execute_cmd('mkdir -p /nvram/debug_overlay/etc')
# pytest.executer.execute_cmd('cp /media/ext1\:/roku_usb/autostart /nvram/debug_overlay/etc')
# roku_ctl.ser.write('\x1A')
# roku_ctl.ser.write('bg')
# pil = PilTool()
# roku_serial = serial_crt(roku_lux.get_note('serial_crt')['port'], roku_lux.get_note('serial_crt')['baud'])


