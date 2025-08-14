# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/21 11:25
# @Author  : chao.li
# @File    : usb_relay.py
import logging
import time

import serial


class UsbRelay:
    cmd = {
        '1': {
            'close': b'\xA0\x01\x01\xA2',
            'release': b'\xA0\x01\x00\xA1'
        },
        '2': {
            'close': b'\xA0\x02\x01\xA3',
            'release': b'\xA0\x02\x00\xA2'
        }
    }

    def __init__(self, com):
        try:
            self.ser = serial.Serial(com, 9600)
            self.alive = True
        except Exception as e:
            # print(f"Can't open {com} Pls check")
            logging.info(f"Can't open {com} Pls check")
        else:
            self.alive = False

    def cmd_filter(self, status, port):
        return self.cmd[port][status]

    def power_control(self, status, hold, port=1):
        '''
        should set power usb control to NC
        Args:
            port:
            status:
            hold:

        Returns:

        '''
        if status == 'off':
            time.sleep(1)
            # self.write(fr'\xA0\x0{port}\x01\xA{port + 1}')
            self.ser.write(self.cmd_filter('close', port))
            time.sleep(hold)
        if status == 'on':
            time.sleep(1)
            # self.write(fr'\xA0\x0{port}\x00\xA{port}')
            self.ser.write(self.cmd_filter('release', port))
            time.sleep(hold)

    def break_make(self, port=1):
        '''

        Args:
            port:

        Returns:

        '''

        # self.ser.write(b'\xA0\x02\x01\xA3')
        self.ser.write(self.cmd_filter('close', str(port)))
        # time.sleep(0.2)
        self.ser.write(self.cmd_filter('release', str(port)))
        # self.ser.write(b'\xA0\x02\x00\xA2')

    def close(self):
        self.ser.close()


# ser = UsbRelay("COM10")
# ser.break_make(port=1)
