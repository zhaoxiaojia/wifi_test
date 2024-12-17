#!/usr/bin/env python 
# -*- coding: utf-8 -*-
# @Time    : 2022/1/5 16:48
# @Author  : chao.li
# @Site    :
# @File    : TestResult.py
# @Software: PyCharm

import csv
import logging
import os
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from matplotlib.backends.backend_pdf import PdfPages

from util.decorators import singleton

plt.rcParams['font.family'] = ['SimHei']


@singleton
class TestResult():
    '''
    Singleton class,should not be inherited
    handle rvr text result

    Attributes:
        logdir : log path
        current_number : current index
        rvr_pdffile : rvr pdf file
        rvr_excelfile : rvr excel file
        log_file : rvr result csv
        detail_file : rvr detail result (contain rssi value)

    '''

    def __init__(self, logdir, step):
        self.logdir = logdir
        self.current_number = 0
        self.x_path = step
        self.x_length = len(self.x_path)

    def init_rvr_result(self):
        self.rvr_excelfile = os.path.join(self.logdir, 'RvrCheckExcel.xlsx')
        if not hasattr(self, 'logFile'):
            self.log_file = os.path.join(self.logdir,
                                         'Rvr' + time.asctime().replace(' ', '_').replace(':', '_') + '.csv')
        if not hasattr(self, 'detialFile'):
            self.detail_file = os.path.join(self.logdir, 'Rvr_Detial.log')
            with open(self.detail_file, 'a', encoding='utf-8') as f:
                f.write("This is rvr test detial data\n")
        with open(self.log_file, 'a', encoding='utf-8') as f:
            title = 'SerianNumber Test_Category	Sub_Category	Coex_Method	BT_WF_Isolation	Standard	Freq_Band	BW	Data_Rate	CH_Freq_MHz	Protocol	Direction	Total_Path_Loss	RxP DB	RSSI Angel	Data_RSSI MCS_Rate Throughput	'
            logging.info(title.split())
            f.write(','.join(title.split()))
            f.write('\n')
        with open(os.path.join(os.getcwd(), 'config\\rvr_wifi_setup.csv' if pytest.win_flag else 'config/rvr_wifi_setup.csv'),
                  'r',encoding='utf-8') as f:
            reader = csv.reader(f)
            self.results_length = []
            for i in [j for j in reader][1:]:
                print(i)
                temp = 0
                if 'tx' in i[-2]:
                    temp += self.x_length
                if 'rx' in i[-2]:
                    temp += self.x_length
                self.results_length.append(temp)

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

    def write_to_excel(self):
        '''
        format csv to excel
        @return: None
        '''
        logging.info('Write to excel')

        df = pd.read_csv(self.log_file, encoding='utf-8')
        # 转置数据
        # df = pd.DataFrame(df.values.T, index=df.columns, columns=df.index)
        if not os.path.exists(self.rvr_excelfile):
            df.to_excel(self.rvr_excelfile, sheet_name=time.asctime().replace(' ', '_').replace(':', '-'))
        else:
            with pd.ExcelWriter(self.rvr_excelfile, engine='openpyxl', mode='a') as f:
                df.to_excel(f, sheet_name=time.asctime().replace(' ', '_').replace(':', '-'))
        logging.info('Write done')

    def write_attenuation_data_to_pdf(self):
        '''
        format excel to pdf
        @return: None
        '''''
        logging.info('Write to pdf')
        with PdfPages(os.path.join(self.logdir, 'RvrResult.pdf')) as rvr_pdffile:
            df = pd.read_excel(self.rvr_excelfile, sheet_name=None)
            all_data = []
            # print(list(df.keys()))
            # ['Fri_Feb_11_16-44-19_2022', 'Fri_Feb_11_16-45-16_2022', 'Fri_Feb_11_16-45-49_2022']
            io = pd.io.excel.ExcelFile(self.rvr_excelfile)
            for i in list(df.keys()):
                all_data.append(pd.read_excel(io, sheet_name=i).values)

            io.close()

            # title = all_data[0][:, 0].tolist()
            all_data = [i.tolist() for i in all_data][0]
            logging.info(f'all_data {all_data}')
            logging.info(f'results_length {self.results_length}')
            temp = 0
            chart_date = []
            for i in self.results_length:
                chart_date.append(all_data[temp:temp + i])
                temp = temp + i
            logging.info(f'chart_data {chart_date}')
            # for i in chart_date:
            #     print(i)
            #     print(len(i))
            plt.figure(figsize=(10, 10))
            plt.suptitle("Rvr test report summary")
            plt.subplots_adjust(wspace=0.3, hspace=0.8)

            for i in chart_date:
                ax = plt.subplot(5, 2, 1 + chart_date.index(i))
                logging.info(f'i {i}')
                # [0, 'P0', 'RvR', 'Standalone', nan, 'Null', '11AX', 5.0, 80, 'Rate_Adaptation', 149, 'TCP', 'UL', nan, nan, -21, nan, 90, 'msc_tx']
                ax.set_title(f'{i[0][7]}_{i[0][6]}_{i[0][8]}_{i[0][10]}')
                # print(i)
                tx_results = []
                rx_results = []
                for j in i:
                    # print(j)
                    if 'UL' in j[-8]:
                        if j[-2] == 'False':
                            print('date wrong')
                            tx_results.append(0)
                        else:
                            tx_results.append(int(j[-2]))
                    else:
                        if j[-2] == 'False':
                            print('data wrong')
                            rx_results.append(0)
                        else:
                            rx_results.append(int(j[-2]))
                # print(rx_results)
                # print(tx_results)
                if tx_results:
                    plt.plot(self.x_path, tx_results, label='tx')
                if rx_results:
                    plt.plot(self.x_path, rx_results, label='rx')
                # plt.plot(self.x_path, [100 for i in range(len(self.x_path))], label='Singal Debility')
                plt.xlabel("Attenuation")
                plt.ylabel("Throughput rate Mb/s")
                plt.legend()
            # plt.show()
            rvr_pdffile.savefig()

    def write_corner_data_to_pdf(self):
        '''
        format excel to pdf
        @return: None
        '''''
        logging.info('Write to pdf')
        with PdfPages(os.path.join(self.logdir, 'RvrCornerResult.pdf')) as rvr_pdffile:
            df = pd.read_excel(self.rvr_excelfile, sheet_name=None)
            all_data = []
            io = pd.io.excel.ExcelFile(self.rvr_excelfile)
            for i in list(df.keys()):
                all_data.append(pd.read_excel(io, sheet_name=i).values)
            io.close()
            # title = all_data[0][:, 0].tolist()
            all_data = [i.tolist() for i in all_data][0]
            temp = 0
            chart_date = []
            for i in self.results_length:
                chart_date.append(all_data[temp:temp + i])
                temp = temp + i
            fig = plt.figure(figsize=(20, 20), dpi=100)
            fig.tight_layout()
            plt.suptitle("Rvr test report summary")
            plt.subplots_adjust(wspace=0, hspace=0.3)
            angles = np.linspace(0, 2 * np.pi, len(self.x_path), endpoint=False)
            angles = np.concatenate((angles, [angles[0]]))
            feature = np.concatenate((self.x_path, [self.x_path[0]]))
            for i in chart_date:
                ax = fig.add_subplot(2, 3, 1 + chart_date.index(i), polar=True)
                # print(i)
                # [0, 'P0', 'RvR', 'Standalone', nan, 'Null', '11AX', 5.0, 80, 'Rate_Adaptation', 149, 'TCP', 'UL', nan, nan, -21, nan, 90, 'msc_tx']
                ax.set_title(f'{i[0][7]}_{i[0][6]}_{i[0][8]}_{i[0][10]}')
                tx_results, rx_results = [], []
                for j in i:
                    if 'UL' in j[-8]:
                        if j[-2] == 'False':
                            print('data wrong')
                            tx_results.append(0)
                        else:
                            tx_results.append(int(j[-2]))
                    else:
                        if j[-2] == 'False':
                            print('data wrong')
                            rx_results.append(0)
                        else:
                            rx_results.append(int(j[-2]))
                if tx_results:
                    tx_results = np.concatenate((tx_results, [tx_results[0]]))
                    ax.plot(angles, tx_results, lw=0.5, label='tx')
                if rx_results:
                    rx_results = np.concatenate((rx_results, [rx_results[0]]))
                    ax.plot(angles, rx_results, lw=0.5, label='rx')
                ax.set_thetagrids(angles * 180 / np.pi, feature)
                ax.set_theta_zero_location('N')
                # ax.set_ylim(0,400)
                ax.set_rlabel_position(0)
                plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=1, frameon=False, )
            # plt.show()
            rvr_pdffile.savefig()

# rvr = RvrResult('D:\windows RVR\wins_wifi',step=[i for i in range(0,40,2)])
# rvr.write_to_excel()
# # rvr.write_corner_data_to_pdf()
# rvr.write_attenuation_data_to_pdf()
