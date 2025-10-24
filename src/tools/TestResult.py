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
from typing import Any, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

plt.rcParams['font.family'] = ['SimHei']


class TestResult():
    """Collect and persist Wi-Fi performance results for each RVR execution."""

    _BASE_HEADERS: Tuple[str, ...] = (
        'SerianNumber',
        'Test_Category',
        'Standard',
        'Freq_Band',
        'BW',
        'Data_Rate',
        'CH_Freq_MHz',
        'Protocol',
        'Direction',
        'Total_Path_Loss',
        'DB',
        'RSSI',
        'Angel',
        'MCS_Rate',
        'Throughput',
        'Expect_Rate',
        'Latency',
        'Packet_Loss',
        'Profile_Mode',
        'Profile_Value',
        'Scenario_Group_Key',
    )

    def __init__(self, logdir, step, repeat_times: int = 0):
        self.logdir = logdir
        self.current_number = 0
        self.x_path = step
        self.x_length = len(self.x_path)
        self._profile_mode: str = ""
        self._profile_value: str = ""
        self._scenario_group_key: str = ""
        try:
            repeat = int(repeat_times)
        except Exception:
            repeat = 0
        self._repeat_times = max(0, repeat)
        self._throughput_header: List[str] = self._build_throughput_header()
        self._headers: List[str] = self._build_header_row()
        self.init_rvr_result()

    def _build_throughput_header(self) -> List[str]:
        total_runs = self._repeat_times + 1
        if total_runs <= 1:
            return ['Throughput']
        return [f'Throughput {index}' for index in range(1, total_runs + 1)]

    def _build_header_row(self) -> List[str]:
        headers: List[str] = []
        for name in self._BASE_HEADERS:
            if name == 'Throughput':
                headers.extend(self._throughput_header)
            else:
                headers.append(name)
        return headers

    def init_rvr_result(self):
        self.rvr_excelfile = os.path.join(self.logdir, 'RvrCheckExcel.xlsx')
        if not hasattr(self, 'logFile'):
            self.log_file = os.path.join(
                self.logdir,
                'Performance' + time.asctime().replace(' ', '_').replace(':', '_') + '.csv',
            )
            with open(self.log_file, 'a', encoding='gb2312') as f:
                f.write(','.join(self._headers))
                f.write("\n")

    def save_result(self, result):
        '''
        write result to log_file
        @param casename: wifi case name
        @param result: tx,rx result
        @return: None
        '''
        logging.info('Writing to csv')
        mode, value = self._get_active_profile_columns()
        scenario_key = self._get_scenario_group_key()
        line = f"{result},{mode},{value},{scenario_key}"
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

    def set_scenario_group_key(self, key: Optional[str]) -> None:
        self._scenario_group_key = self._normalize_scenario_group_key(key)

    def clear_scenario_group_key(self) -> None:
        self._scenario_group_key = ""

    # internal helpers
    def _get_active_profile_columns(self) -> Tuple[str, str]:
        return self._profile_mode, self._profile_value

    def _get_scenario_group_key(self) -> str:
        return self._scenario_group_key

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

    @staticmethod
    def _normalize_scenario_group_key(key: Optional[str]) -> str:
        if key is None:
            return ""
        text = str(key).strip()
        if not text:
            return ""
        sanitized = text.replace('\r', ' ').replace('\n', ' ')
        sanitized = sanitized.replace(',', '_')
        return sanitized.strip()


# rvr = RvrResult('D:\windows RVR\wins_wifi',step=[i for i in range(0,40,2)])
# rvr.write_to_excel()
# # rvr.write_corner_data_to_pdf()
# rvr.write_attenuation_data_to_pdf()
