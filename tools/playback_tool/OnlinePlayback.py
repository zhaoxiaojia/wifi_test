# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/19 10:30
# @Author  : chao.li
# @File    : OnlinePlayback.p

import logging
import os
import re
import signal
import subprocess
import threading
import time


from tools.connect_tool.adb import ADB
from tools.decorators import set_timeout



class Online(ADB):
    '''
    Online video playback

    Attributes:
        DECODE_TAG : logcat tag
        DECODE_TAG_AndroidS : logcat tag
        PLAYER_PACKAGE_TUPLE : player package tuple

    '''

    DECODE_TAG = 'AmlogicVideoDecoderAwesome'
    DECODE_TAG_AndroidS = 'VDA'
    PLAYER_PACKAGE_TUPLE = '', ''

    def __init__(self, name=''):
        super(Online, self).__init__('OnlinePlayback')

    def playback(self, activity, link):
        '''
        start apk
        am start -n xxx
        @param activity: activity name
        @param link: video link
        @return:
        '''
        logging.info(activity.format(link))
        self.checkoutput(activity.format(link))

    def time_out(self):
        '''
        kill logcat process
        clear logcat
        @return:
        '''
        logging.warning('Time over!')
        # if hasattr(self, 'logcat') and isinstance(self.logcat, subprocess.Popen):
        #     os.kill(self.logcat.pid, signal.SIGTERM)
        #     self.logcat.terminate()
        # self.clear_logcat()

    @set_timeout(300, time_out)
    def check_playback_status(self):
        '''
        Waiting for network load video
        @return: True (When video is playing) or error (Timeout) : boolean
        '''

        return True

    def check_apk_exist(self):
        '''
        check apk status
        @return: apk status : boolean
        '''
        return True if self.PLAYER_PACKAGE_TUPLE[0] in self.checkoutput('ls /data/data/') else False