#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: rs_test.py 
@time: 2025/3/11 11:07 
@desc: 
'''


import logging
import subprocess
from src.util.decorators import singleton


@singleton
class rs:
    def __init__(self):
        self.rf_path = 'res/AmlACUControl.exe'
        self.corner_path = 'res/AmlSunveyController.exe'

    def execute_rf_cmd(self, num):
        exe_path = f'{self.rf_path} {num}'
        subprocess.run(exe_path, capture_output=True, text=True)
        self.rf = num

    def get_rf_current_value(self):
        return self.rf

    def get_turntanle_current_angle(self):
        return self.current_angle

    def set_turntable_zero(self):
        self.execute_turntable_cmd('', 0)

    def execute_turntable_cmd(self, type, angle=''):
        # 调用 AutoIt 编译的 .exe 文件
        exe_path = f"{self.corner_path} -angle {angle}"  # 替换为你的 .exe 文件路径
        result = subprocess.run(exe_path, capture_output=True, text=True)

        # 获取输出
        output = result.stdout.strip()  # 去除多余的空白字符

        # 解析输出
        if "|" in output:
            self.current_angle, self.current_distance = output.split("|")
            logging.info(f"Current Angle: {self.current_angle}")
            logging.info(f"Current Distance: {self.current_distance}")
        else:
            logging.info("Failed to parse output:", output)
