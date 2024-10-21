# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/21 11:25
# @Author  : chao.li
# @File    : usb_relay.py
import time

import serial
import logging


class UsbRelay:
    def __init__(self, com):
        try:
            self.ser = serial.Serial(com, 9600)
            self.alive = True
        except Exception as e:
            print(f"Can't open {com} Pls check")
            logging.info(f"Can't open {com} Pls check")
        else:
            self.alive = False

    def break_make(self, hold):
        if self.alive:
            self.ser.write(b'\xA0\x01\x01\xA2')
            time.sleep(hold)
            self.ser.write(b'\xA0\x01\x01\xA1')
