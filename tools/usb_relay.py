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

    def power_control(self, status, hold):
        '''
        should set power usb control to NC
        Args:
            status:
            hold:

        Returns:

        '''
        if status == 'off':
            time.sleep(1)
            self.ser.write(b'\xA0\x01\x01\xA2')
            time.sleep(hold)
        if status == 'on':
            time.sleep(1)
            self.ser.write(b'\xA0\x01\x00\xA1')
            time.sleep(hold)

    def break_make(self):
        '''
        should set button usb control to NO
        Returns:

        '''
        self.ser.write(b'\xA0\x01\x00\xA1')
        time.sleep(0.2)
        self.ser.write(b'\xA0\x01\x01\xA2')

    def close(self):
        self.ser.close()