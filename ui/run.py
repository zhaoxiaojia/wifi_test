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

from PyQt5.QtWidgets import QVBoxLayout, QTextEdit
from qfluentwidgets import (
    CardWidget,
    StrongBodyLabel,
    PushButton,
    ProgressBar,
    InfoBar,
    InfoBarPosition,
    FluentIcon,
)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor
import subprocess
import datetime


class CaseRunner(QThread):
    """Thread to run pytest and emit log output"""

    log_signal = pyqtSignal(str)

    def __init__(self, case_path: str, parent=None):
        super().__init__(parent)
        self.case_path = case_path

    def run(self) -> None:
        timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
        cmd = [
            "python",
            "-m",
            "pytest",
            "-v",
            "-s",
            "--capture=sys",
            "--html=report.html",
            "--full-trace",
            f"--resultpath={timestamp}",
            self.case_path,
        ]
        cmd = " ".join(cmd)
        print(cmd)
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            shell=True
        )

        if process.stdout:
            for line in process.stdout:
                self.log_signal.emit(line.rstrip())
        if process.stdout:
            process.stdout.close()
        process.wait()

        self.log_signal.emit("<b style='color:green;'>运行完成！</b>")


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
        self.log_area.setMinimumHeight(400)
        self.log_area.setStyleSheet("font-size:16px; color:#2b2b2b; background:#fafaff;")
        self.log_area.document().setMaximumBlockCount(2000)
        layout.addWidget(self.log_area, stretch=5)

        self.back_btn = PushButton("返回", self)
        self.back_btn.setIcon(FluentIcon.LEFT_ARROW)
        self.back_btn.clicked.connect(self.on_back)
        layout.addWidget(self.back_btn)
        self.setLayout(layout)

        self.run_case()

    def _append_log(self, msg: str):
        color = None
        upper_msg = msg.upper()
        if "ERROR" in upper_msg:
            color = "red"
        elif "WARNING" in upper_msg:
            color = "orange"
        elif "INFO" in upper_msg:
            color = "blue"

        html = f"<span style='color:{color};'>{msg}</span>" if color else msg
        self.log_area.append(html)

        doc = self.log_area.document()
        if doc.blockCount() > 5000:
            cursor = QTextCursor(doc.firstBlock())
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def run_case(self):
        self.runner = CaseRunner(self.case_path)
        self.runner.log_signal.connect(self._append_log)
        self.runner.finished.connect(
            lambda: InfoBar.success(
                title="完成",
                content="用例运行已完成",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=1800,
            )
        )
        self.runner.start()

    def on_back(self):
        self.on_back_callback()
