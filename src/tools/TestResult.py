#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2022/1/5 16:48
# @Author  : chao.li
# @Site    :
# @File    : TestResult.py
# @Software: PyCharm

import logging
import os
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

plt.rcParams['font.family'] = ['SimHei']


class TestResult():
    '''
    Singleton class,should not be inherited
    handle rvr text result

    Attributes:
        logdir : log path
        current_number : current index
        rvr_pdffile : rvr pdf file
        rvr_excelfile : rvr excel file
        log_file : performance result csv
        detail_file : rvr detail result (contain rssi value)

    '''

    def __init__(self, logdir, step):
        self.logdir = logdir
        self.current_number = 0
        self.x_path = step
        self.x_length = len(self.x_path)
        self.init_rvr_result()

    def init_rvr_result(self):
        self.rvr_excelfile = os.path.join(self.logdir, 'RvrCheckExcel.xlsx')
        if not hasattr(self, 'logFile'):
            self.log_file = os.path.join(
                self.logdir,
                'Performance' + time.asctime().replace(' ', '_').replace(':', '_') + '.csv',
            )
            with open(self.log_file, 'a', encoding='gb2312') as f:
                title = (
                    'SerianNumber Test_Category Standard Freq_Band BW Data_Rate '
                    'CH_Freq_MHz Protocol Direction Total_Path_Loss DB RSSI Angel '
                    'MCS_Rate Throughput Expect_Rate '
                )
                f.write(','.join(title.split()))
                f.write('\n')


    def save_result(self, result):
        '''
        write result to log_file
        @param casename: wifi case name
        @param result: tx,rx result
        @return: None
        '''
        logging.info('Writing to csv')
        with open(self.log_file, 'a') as f:
            f.write(result)
            f.write('\n')
        logging.info('Write done')


# rvr = RvrResult('D:\windows RVR\wins_wifi',step=[i for i in range(0,40,2)])
# rvr.write_to_excel()
# # rvr.write_corner_data_to_pdf()
# rvr.write_attenuation_data_to_pdf()
