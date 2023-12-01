#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2022/4/27 10:08
# @Author  : chao.li
# @Site    :
# @File    : UiautomatorTool.py
# @Software: PyCharm

import logging
import time

import uiautomator2 as u2
from uiautomator import Device


class UiautomatorTool:
    '''
    Singleton class,should not be inherited
    Uiautomator2 instance

    Attributes:
        d : uiautomator2 instance

    '''

    def __init__(self, serialnumber, type="u2"):
        if type == "u2":
            self.d2 = u2.connect(serialnumber)
        else:
            self.d1 = Device(serialnumber)
        # logging.debug(f'device info {self.d.info}')

    def __new__(cls, *args, **kwargs):
        if not hasattr(UiautomatorTool, "_instance"):
            if not hasattr(UiautomatorTool, "_instance"):
                UiautomatorTool._instance = object.__new__(cls)
        return UiautomatorTool._instance

    def wait(self, text):
        '''
        wait for widget
        @param text: widget text name
        @return: None
        '''
        logging.info(f'waiting for {text}')
        for _ in range(5):
            if self.d2.exists(text=text):
                self.d2(text=text).click()
                return 1
            time.sleep(1)
        logging.debug('not click')

    def wait_not_exist(self, text):
        '''
        wait not exist widget
        @param text: widget text name
        @return: None
        '''
        logging.info(f'waiting for {text} disappear')
        for _ in range(5):
            if not self.d2.exists(text=text):
                return 1
            time.sleep(1)
        logging.info('still exists')

    def send_keys(self, searchKey, attribute):
        '''
        input text in widget
        @param searchKey: widget name
        @param attribute: text
        @return: None
        '''
        if self.d2.exists(resourceId=searchKey):
            self.d2(resourceId=searchKey).send_keys(attribute)
        if self.d2.exists(text=searchKey):
            self.d2(text=searchKey).send_keys(attribute)
