# !/usr/bin/env python
# -*-coding:utf-8 -*-

import datetime
import json
import logging
import os
import shutil
import subprocess
import sys
import time

from PyQt6.QtWidgets import QApplication, QStackedWidget
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition
from ui.windows_case_config import CaseConfigPage
from ui.run import RunPage
import pytest
from qfluentwidgets import setTheme, Theme
from PyQt6.QtGui import QGuiApplication
from case_handle import testCase

timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
# test_case = 'test/project/roku/test_demo.py'
test_case = 'test/test_wifi_peak_throughput.py'

report_parent_path = test_case.replace('test', 'report', 1)

if isinstance(test_case, str):
    if os.path.isdir(test_case):
        allure_cmd = f'--alluredir=./results/allure/{test_case.split("test/")[1]}'
    if os.path.isfile(test_case):
        allure_cmd = f'--alluredir=./allure'

allure_path = fr'./report/{test_case.split("test/")[1]}/{timestamp}'
report_path = fr'./report/{timestamp}'
allure_history_file = ''


# 获取下一个文件夹的名称，以及最近一个趋势的数据
def get_dir():
    if allure_history_file:
        history_file = os.path.join(report_parent_path, os.listdir(report_parent_path)[-1],
                                    "widgets/history-trend.json")
        buildOrder = len(allure_history_file)
        # 取出最近一次执行的历史趋势的json
        with open(history_file, 'r+') as f:
            data = json.load(f)
            data[0]['buildOrder'] = buildOrder
            data[0]['reportUrl'] = 'http://todo.com'
        with open(history_file, 'w+') as f:
            json.dump(data, f)
        # 将这次生成的文件夹序号以及最新的历史趋势数据返回
        return buildOrder, data
    return 0, None


def update_file():
    dict = []
    for i in allure_history_file:
        print(i)
        file = os.path.join(report_parent_path, i, "widgets", "history-trend.json")
        with open(file) as f:
            temp_data = json.load(f)
            if not dict:
                dict.append(temp_data[0])
                continue
            if temp_data[0]['buildOrder'] not in [i['buildOrder'] for i in dict]:
                dict.append(temp_data[0])
    dict.sort(key=lambda x: x['buildOrder'], reverse=True)
    latest_file = os.path.join(report_parent_path + '/' + allure_history_file[-1] + "/widgets/history-trend.json")
    with open(latest_file, 'w') as f:
        json.dump(dict, f)


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Amlogic Wi-Fi Test Tool")
        self.resize(1400, 1200)
        self.setMinimumSize(1400, 1200)
        self.center_window()

        # 页面实例化
        self.case_config_page = CaseConfigPage(self.on_run)
        self.run_page = None  # 运行窗口动态加载

        # 添加侧边导航（页面，图标，标题，描述）
        self.addSubInterface(
            self.case_config_page, FluentIcon.SETTING, "用例配置", "Case Config"
        )
        # 可加更多页面，比如“历史记录”“关于”等

        # FluentWindow自带自定义颜色与主题
        setTheme(Theme.LIGHT)   # 或 Theme.LIGHT
        # self.setMicaEffectEnabled(True)  # Win11下生效毛玻璃
    def center_window(self):
        # 获取屏幕的几何信息
        screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
        # 获取窗口的几何信息
        window_geometry = self.frameGeometry()
        # 计算屏幕中心位置
        center_point = screen_geometry.center()
        # 将窗口中心移动到屏幕中心
        window_geometry.moveCenter(center_point)
        # 确保窗口顶部不会超出屏幕
        self.move(window_geometry.topLeft())
    def on_run(self, case_path, config):
        # 切换到run页面（传参）
        if self.run_page:
            self.removeSubInterface(self.run_page)
        self.run_page = RunPage(case_path, config, self.show_case_config)
        self.addSubInterface(
            self.run_page, FluentIcon.PLAY, "运行", "Run",
            position=NavigationItemPosition.BOTTOM
        )
        self.setCurrentIndex(self.run_page)

    def show_case_config(self):
        self.setCurrentIndex(self.case_config_page)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
    '''
   
    if not os.path.exists('report'):
        os.mkdir('report')
    # if os.path.exists('assets'):
    #     shutil.rmtree('assets')
    if not os.path.exists(report_path):
        os.mkdir(report_path)

    testcase_handler = testCase()
    # caselist = coco.sync_testSuite(suite='stability', case=r'test_03_open_wifi.py')
    # test_case = [f'.\\{i}' for i in caselist]
    cmd = ['-v', '-s', '--capture=sys', '--html=report.html','--full-trace', f'--resultpath={timestamp}']
    # cmd = ['-v', '--capture=sys', '--full-trace', '--html=report.html', f'--resultpath={timestamp}', allure_cmd];
    # print(" ".join(cmd))
    if type(test_case) == str:
        test_case = [test_case];
    pytest.main(cmd + test_case);

    # if locals().get('allure_cmd'):
    #     subprocess.check_output(f'allure generate -c ./allure -o {allure_path}', shell=True);
    #     # allure_history_file = os.listdir(report_parent_path);
    #     # get_dir();
    #     # update_file();
    #     os.system(f'allure open {allure_path}')
    '''