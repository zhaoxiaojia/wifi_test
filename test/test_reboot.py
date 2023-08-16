# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : test_reboot.py
# Time       ：2023/8/15 10:19
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""



import pytest

'''
测试步骤
1.连接ssid
2.改变带宽
3.播放youtube
重复1-3
'''

@pytest.mark.repeat(5000)
def test_reboot():
    pytest.executer.reboot()
    pytest.executer.wait_devices()
    pytest.executer.wait_for_wifi_service()
    pytest.executer.wait_for_wifi_address()
    pytest.executer.enter_wifi_activity()
