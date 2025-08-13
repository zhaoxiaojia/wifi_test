#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: test_T6473243.py
@time: 2025/7/31 17:05 
@desc: 
'''



import logging
import time
import pytest


'''
Test Network - When Internet/DNS is Not Available 

Pre step:

Test step
1) Connect to Wireless
2) Remove WAN cable from Router
3) Navigate to UI > Settings > Network > Check connection

Expected ResulÍ
Verify that the DUT displays UI dialog the internet light check failed
'''

@pytest.fixture(autouse=True)
def setup():
    yield


def test_wifi_switch(request):
    pytest.dut.roku.enter_wifi()
    pytest.dut.roku.ir_enter('Set up connection', 'LabelListItem')
    pytest.dut.roku.capture_screen(pytest.testResult.logdir+"/T6473243.png")
