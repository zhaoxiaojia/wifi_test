# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/9/10 13:30
# @Author  : chao.li
# @File    : ixchariot.py

import logging
import os
import re
import subprocess
import time


class ix:
    def __init__(self, ep1="", ep2="", pair=""):
        self.ep1 = ep1
        self.ep2 = ep2
        self.pair = pair
        self.script_path = os.getcwd() + '/script/rvr.tcl'
        # self.script_path = r'D:\PycharmProjects\wifi_test\script\rvr.tcl'

    def run_rvr(self, ep1="", ep2="", pair=""):
        if ep1: self.ep1 = ep1
        if ep2: self.ep2 = ep2
        if pair: self.pair = pair

        res = subprocess.Popen(f"tclsh {self.script_path} {self.ep1} {self.ep2} {self.pair}", shell=True,
                               stdout=subprocess.PIPE, encoding='utf-8')
        time.sleep(40)
        # if res.poll() == 0:
        info = res.stdout.read()
        logging.info(info)
        date = re.findall(r'avg \d+\.\d+', info, re.S)
        return date[0] if date else False

    def modify_tcl_script(self, old_str, new_str):
        file = './script/rvr.tcl'
        with open(file, "r", encoding="utf-8") as f1, open("%s.bak" % file, "w", encoding="utf-8") as f2:
            for line in f1:
                if old_str in line:
                    line = new_str
                f2.write(line)
        os.remove(file)
        os.rename("%s.bak" % file, file)
