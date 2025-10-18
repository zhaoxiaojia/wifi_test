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
from typing import Any, Optional, Tuple

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
        self._profile_mode: str = ""
        self._profile_value: str = ""
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
                    'MCS_Rate Throughput Expect_Rate Profile_Mode Profile_Value '
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
        mode, value = self._get_active_profile_columns()
        line = f"{result},{mode},{value}"
        with open(self.log_file, 'a') as f:
            f.write(line)
            f.write('\n')
        logging.info('Write done')

    # --- profile helpers -------------------------------------------------
    def set_active_profile(self, mode: Optional[str], value: Any) -> None:
        normalized_mode = self._normalize_profile_mode(mode)
        normalized_value = self._normalize_profile_value(value)
        if normalized_mode == "" and normalized_value != "":
            normalized_mode = "CUSTOM"
        self._profile_mode = normalized_mode
        self._profile_value = normalized_value

    def clear_active_profile(self) -> None:
        self._profile_mode = ""
        self._profile_value = ""

    # internal helpers
    def _get_active_profile_columns(self) -> Tuple[str, str]:
        return self._profile_mode, self._profile_value

    @staticmethod
    def _normalize_profile_mode(mode: Optional[str]) -> str:
        if mode is None:
            return ""
        text = str(mode).strip().lower()
        if not text:
            return ""
        if text in {"target", "target_rssi", "rvo_target"}:
            return "TARGET_RSSI"
        if text in {"static", "static_db", "rvo_static"}:
            return "STATIC_DB"
        if text in {"default", "normal"}:
            return "DEFAULT"
        return text.upper()

    @staticmethod
    def _normalize_profile_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple, set)):
            items = [TestResult._normalize_profile_value(item) for item in value]
            items = [item for item in items if item]
            return items[0] if items else ""
        text = str(value).strip()
        if not text:
            return ""
        try:
            number = float(text)
        except ValueError:
            return text
        if number.is_integer():
            return str(int(number))
        return f"{number:.2f}".rstrip('0').rstrip('.')


# rvr = RvrResult('D:\windows RVR\wins_wifi',step=[i for i in range(0,40,2)])
# rvr.write_to_excel()
# # rvr.write_corner_data_to_pdf()
# rvr.write_attenuation_data_to_pdf()
