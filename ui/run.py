#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: run.py 
@time: 2025/7/22 22:02 
@desc: 
'''

# ui/run.py

from PyQt5.QtWidgets import QVBoxLayout
from qfluentwidgets import CardWidget, StrongBodyLabel, PushButton, ProgressBar, InfoBar, InfoBarPosition
from PyQt5.QtWidgets import QTextEdit
from qfluentwidgets import FluentIcon
import threading
import time
import subprocess
import datetime


class RunPage(CardWidget):
    """运行页"""

    def __init__(self, case_path, config, on_back_callback):
        super().__init__()
        self.setObjectName("runPage")
        self.case_path = case_path
        self.config = config
        self.on_back_callback = on_back_callback

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addWidget(StrongBodyLabel(f"正在运行：{case_path}"))

        self.progress = ProgressBar(self)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.log_area = QTextEdit(self)
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(240)
        self.log_area.setStyleSheet("font-size:16px; color:#2b2b2b; background:#fafaff;")
        layout.addWidget(self.log_area)

        self.back_btn = PushButton("返回", self)
        self.back_btn.setIcon(FluentIcon.LEFT_ARROW)
        self.back_btn.clicked.connect(self.on_back)
        layout.addWidget(self.back_btn)
        self.setLayout(layout)

        self.run_case()

    def append_log(self, msg):
        self.log_area.append(msg)

    def run_case(self):
        def execute_case():
            timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
            report_path = fr'./report/{timestamp}'
            cmd = ["pytest", "-v", '-s', '--capture=sys', '--html=report.html', '--full-trace',
                   f'--resultpath={timestamp}', self.case_path]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # 实时读取输出
            for line in process.stdout:
                self.append_log(line.rstrip())
            process.stdout.close()
            process.wait()

            self.append_log("<b style='color:green;'>运行完成！</b>")
            InfoBar.success(
                title="完成",
                content="用例运行已完成",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=1800
            )

        threading.Thread(target=execute_case, daemon=True).start()

    def on_back(self):
        self.on_back_callback()
