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
import logging

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
import re
import time
import os
import random
import sys
from pathlib import Path
import traceback
import threading
import pytest
import io


class LiveLogWriter:
    """自定义stdout/err实时回调到信号"""

    def __init__(self, emit_func):
        self.emit_func = emit_func
        self._lock = threading.Lock()
        self._buffer = ""

    def write(self, msg):
        # 保证分行和进度信号捕获
        with self._lock:
            self._buffer += msg
            while '\n' in self._buffer:
                line, self._buffer = self._buffer.split('\n', 1)
                self.emit_func(line.rstrip('\r'))

    def flush(self):
        """将缓冲区剩余内容输出"""
        with self._lock:
            if self._buffer:
                self.emit_func(self._buffer.rstrip('\r'))
                self._buffer = ""

    def isatty(self):
        return False  # 必须加上这个

    def fileno(self):
        raise io.UnsupportedOperation("Not a real file")


class CaseRunner(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, case_path: str, parent=None):
        super().__init__(parent)
        self.case_path = case_path
        self._should_stop = False

    def run(self):
        # 日志、进度写到窗口
        try:
            timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
            timestamp = f"{timestamp}_{random.randint(1000, 9999)}"
            report_dir = os.path.abspath(os.path.join(os.getcwd(), f"report/{timestamp}"))
            os.makedirs(report_dir, exist_ok=True)
            pytest_args = [
                "-v",
                "-s",
                "--full-trace",
                f"--resultpath={report_dir}",
                self.case_path,
            ]

            # 实时日志到窗口
            def emit_log(line):
                self.log_signal.emit(line)
                # 解析进度
                match = re.search(r"\[PYQT_PROGRESS\]\s+(\d+)/(\d+)", line)
                if match:
                    finished = int(match.group(1))
                    total = int(match.group(2))
                    percent = int(finished / total * 100)
                    self.progress_signal.emit(percent)

            writer = LiveLogWriter(emit_log)
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = writer

            # 重新配置 logging，将输出重定向到 writer
            root_logger = logging.getLogger()
            old_handlers = root_logger.handlers[:]
            old_level = root_logger.level
            for h in old_handlers:
                root_logger.removeHandler(h)
            stream_handler = logging.StreamHandler(writer)
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(filename)s:%(funcName)s(line:%(lineno)d) |  %(message)s",
                "%Y-%m-%d %H:%M:%S",
            )
            stream_handler.setFormatter(formatter)
            root_logger.addHandler(stream_handler)
            root_logger.setLevel(logging.INFO)

            # 主线程里定期检查_should_stop可实现停止功能
            try:
                self.log_signal.emit(f"<b style='color:blue;'>开始执行pytest: {' '.join(pytest_args)}</b>")
                code = pytest.main(pytest_args)
                if not self._should_stop:
                    self.log_signal.emit("<b style='color:green;'>运行完成！</b>")
                else:
                    self.log_signal.emit("<b style='color:red;'>运行已终止！</b>")
            finally:
                logging.info(traceback.format_exc())
                for h in root_logger.handlers[:]:
                    root_logger.removeHandler(h)
                for h in old_handlers:
                    root_logger.addHandler(h)
                root_logger.setLevel(old_level)

                sys.stdout = old_stdout
                sys.stderr = old_stderr

        except Exception as e:
            tb = traceback.format_exc()
            self.log_signal.emit(f"<b style='color:red;'>执行失败：{str(e)}</b>")
            self.log_signal.emit(f"<pre>{tb}</pre>")

    def stop(self):
        # NOTE: pytest没有优雅的“中止”API，通常不能强停，最优雅还是用子进程方案
        self._should_stop = True
        # 这里没有强制中止机制（如果用例本身卡死会无效）


class RunPage(CardWidget):
    """运行页"""

    def __init__(self, case_path, display_case_path=None, config=None, on_back_callback=None, parent=None):
        super().__init__(parent)
        self.setObjectName("runPage")
        self.case_path = case_path
        self.config = config
        self.on_back_callback = on_back_callback
        self.main_window = parent  # 保存主窗口引用（用于InfoBar父窗口）

        needs_recalc = False
        if not display_case_path:
            needs_recalc = True
        else:
            p = Path(display_case_path)
            if ".." in p.parts or p.drive or p.is_absolute():
                needs_recalc = True
        if needs_recalc:
            app_base = self._get_application_base()
            display_case_path = Path(case_path).resolve()
            try:
                display_case_path = display_case_path.relative_to(app_base)
            except ValueError:
                pass
            display_case_path = display_case_path.as_posix()
        else:
            display_case_path = display_case_path.replace("\\", "/")
        self.display_case_path = display_case_path

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addWidget(StrongBodyLabel(self.display_case_path))

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
        self.runner.progress_signal.connect(self.update_progress)
        # 关键修改：InfoBar的父窗口改为主窗口（而非RunPage自身）
        self.runner.finished.connect(
            lambda: InfoBar.success(
                title="完成",
                content="用例运行已完成",
                parent=self.main_window,  # 这里改为主窗口
                position=InfoBarPosition.TOP,
                duration=1800,
            )
        )
        self.runner.start()

    def on_back(self):
        if hasattr(self, "runner") and self.runner:
            # 停止线程并等待有限时间
            self.runner.stop()
            finished = self.runner.wait(3000)
            if not finished:
                # 若仍未结束，尝试强制退出
                self.runner.quit()
                if not self.runner.wait(1000):
                    self._append_log("<b style='color:red;'>线程结束超时，可能仍在后台运行</b>")
            # 断开所有信号
            try:
                self.runner.log_signal.disconnect(self._append_log)
            except (TypeError, RuntimeError):
                pass
            try:
                self.runner.progress_signal.disconnect(self.update_progress)
            except (TypeError, RuntimeError):
                pass
            try:
                self.runner.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.runner = None  # 清除引用

        # 先断开自身所有信号再返回
        try:
            self.disconnect()
        except TypeError:
            pass

        self.on_back_callback()  # 调用返回配置页的回调

    def _get_application_base(self) -> Path:
        """获取应用根路径"""
        base = (
            Path(sys._MEIPASS) / "src"
            if hasattr(sys, "_MEIPASS")
            else Path(__file__).resolve().parent.parent
        )
        return base.resolve()
