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

from PyQt5.QtWidgets import QVBoxLayout, QTextEdit, QLabel, QFrame
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
from PyQt5.QtWidgets import QProgressBar
import subprocess
import datetime
import sys
import re


class CaseRunner(QThread):
    """Thread to run pytest and emit log output"""

    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)  # 新增：用于进度条

    def __init__(self, case_path: str, parent=None):
        super().__init__(parent)
        self.case_path = case_path
        self._process = None  # 保存子进程对象
        self._should_stop = False

    def run(self) -> None:
        timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
        cmd = [
            sys.executable, "-u",
            "-m",
            "pytest",
            "-v",
            "-s",
            "--html=report.html",
            "--full-trace",
            f"--resultpath={timestamp}",
            self.case_path,
        ]
        self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         universal_newlines=True, encoding="utf-8", bufsize=1)

        for line in self._process.stdout:
            self.log_signal.emit(line.rstrip())
            match = re.search(r"\[PYQT_PROGRESS\]\s+(\d+)/(\d+)", line)
            if match:
                # print(f"[MATCH] {match.group(1)}/{match.group(2)}")
                finished = int(match.group(1))
                total = int(match.group(2))
                percent = int(finished / total * 100)
                # print(f"[EMIT] {percent}%")
                self.progress_signal.emit(percent)
        self._process.stdout.close()
        self._process.wait()
        self.log_signal.emit("<b style='color:green;'>运行完成！</b>")

    def stop(self):
        self._should_stop = True
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                print(f"Terminate {self._process} terminate")
            except Exception as e:
                print(f"Terminate failed: {e}")


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

        # 文本进度标签
        self.progress_text = QLabel("当前进度 0%", self)
        self.progress_text.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.progress_text)
        # 外部容器（透明）
        self.progress_container = QFrame(self)
        self.progress_container.setFixedHeight(10)
        self.progress_container.setStyleSheet("background: transparent;")
        layout.addWidget(self.progress_container)

        # 内部进度块
        self.progress_chunk = QFrame(self.progress_container)
        self.progress_chunk.setFixedHeight(10)
        self.progress_chunk.setStyleSheet("""
            background-color: #A2D2FF;
            border-radius: 4px;
        """)
        self.progress_chunk.setFixedWidth(0)
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            # 从标签中提取当前百分比
            text = self.progress_text.text()
            percent = int(text.split()[-1].rstrip('%'))
            self.update_progress(percent)
        except Exception:
            pass

    def update_progress(self, percent):
        self.progress_text.setText(f"当前进度 {percent}%")
        total_width = self.progress_container.width() or 300  # 默认宽度
        progress_width = int(total_width * percent / 100)
        # 更新进度块宽度
        self.progress_chunk.setFixedWidth(progress_width)

    def run_case(self):
        self.runner = CaseRunner(self.case_path)
        self.runner.log_signal.connect(self._append_log)
        self.runner.progress_signal.connect(self.update_progress)  # 新增
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
        if hasattr(self, "runner"):
            self.runner.stop()
        self.on_back_callback()
