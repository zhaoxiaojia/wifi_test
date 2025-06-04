#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: test_demo.py 
@time: 2025/2/12 10:58 
@desc: 
'''
import logging
import time

import pytest
from dut_control.roku_ctrl import roku_ctrl

'''
Pre step:


Test step


Expected Result
'''

# @pytest.fixture(autouse=True)
# def setup():
#     pytest.dut.checkoutput('config_set fw.fastboot.capture.snapshot true')
#     pytest.dut.reboot()
#     yield

ssid = ['TNCAPFE09C7_5G', 'TNCAPFE09C7_2.4G']  # ,'Linksys-MR-5G','Linksys-MR-2.4G']
# ssid = ['Linksys-MR-5G','Linksys-MR-2.4G']
passwd = ['123456789', '123456789']  # ,'11112222','']


# passwd = ['11112222','']
@pytest.mark.repeat(10)
def test_wifi_switch(request):
    mark = request.node.get_closest_marker("repeat")
    if mark is None:
        current_repeat = 1
    else:
        repeat_count = mark.args[0]
        if not hasattr(request.node, "_repeat_count"):
            request.node._repeat_count = 0
        request.node._repeat_count += 1
        current_repeat = request.node._repeat_count
    logging.info('start to switch wifi')
    # 连接wifi
    assert pytest.dut.roku.wifi_conn(ssid[current_repeat % 4], passwd[current_repeat % 4]), "Can't connect target ssid"
    # # 重启
    pytest.dut.reboot()
    pytest.dut.roku = roku_ctrl(pytest.dut.roku.ip)
    # 播放 player
    pytest.dut.roku['837'].launch()
    time.sleep(5)
    pytest.dut.roku.select()
    pytest.dut.checkoutput('cat /sys/class/vdec/vdec_status')
    pytest.dut.checkoutput('cat /proc/asound/card0/pcm*p/sub0/status')
    time.sleep(30)
