# !/usr/bin/env python
# -*-coding:utf-8 -*-

import os

import pytest
import datetime
import json
import subprocess

timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
test_case = 'test/test_rvr.py'

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


if __name__ == '__main__':

    if not os.path.exists('report'):
        os.mkdir('report')

    if not os.path.exists(report_path):
        os.mkdir(report_path)

    cmd = ['-v', '--capture=sys', '--full-trace', '--html=report.html', f'--resultpath={timestamp}', test_case,
           allure_cmd]
    print(" ".join(cmd))
    pytest.main(cmd)
    # os.system("allure generate -c results/ -o allure-report/")
    if allure_cmd:
        subprocess.check_output(f'allure generate -c ./allure -o {allure_path}', shell=True)
        allure_history_file = os.listdir(report_parent_path)
        get_dir()
        update_file()
    os.system(f'allure serve ./allure')
