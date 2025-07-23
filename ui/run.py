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

from PyQt6.QtWidgets import QVBoxLayout
from qfluentwidgets import CardWidget, StrongBodyLabel, PushButton, ProgressBar, InfoBar, InfoBarPosition
from PyQt6.QtWidgets import QTextEdit
from qfluentwidgets import FluentIcon
import threading
import time

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
        self.back_btn.setIcon(FluentIcon.BACK)
        self.back_btn.clicked.connect(self.on_back)
        layout.addWidget(self.back_btn)
        self.setLayout(layout)

        self.run_case()

    def append_log(self, msg):
        self.log_area.append(msg)

    def run_case(self):
        def fake_run():
            for i in range(0, 101, 10):
                self.progress.setValue(i)
                self.append_log(f"<b style='color:#2770FF;'>进度: {i}%</b>")
                time.sleep(0.15)
            self.append_log("<b style='color:green;'>运行完成！</b>")
            InfoBar.success(
                title="完成",
                content="用例运行已完成",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=1800
            )
        threading.Thread(target=fake_run, daemon=True).start()

    def on_back(self):
        self.on_back_callback()
