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
import re
import time
import os
import random
import sys
from pathlib import Path
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

        report_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../report")
        )
        os.makedirs(report_root, exist_ok=True)

        # 2. 唯一子目录名
        timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
        timestamp = f"{timestamp}_{random.randint(1000, 9999)}"
        report_dir = os.path.join(report_root, timestamp)
        os.makedirs(report_dir, exist_ok=True)
        pytest_args = [
            "-v",
            "-s",
            "--full-trace",
            f"--resultpath={report_dir}",
            self.case_path,
        ]

        try:
            self._process = subprocess.Popen(
                ["pytest", *pytest_args],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            while True:
                if self._should_stop:
                    self.log_signal.emit("<b style='color:orange;'>检测到停止信号，正在终止...</b>")
                    if self._process.poll() is None:
                        self._process.terminate()
                        try:
                            self._process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            self._process.kill()
                    break

                line = self._process.stdout.readline()
                if not line:
                    if self._process.poll() is not None:
                        break
                    time.sleep(0.1)
                    continue

                line = line.rstrip()
                self.log_signal.emit(line)
                match = re.search(r"\[PYQT_PROGRESS\]\s+(\d+)/(\d+)", line)
                if match:
                    finished = int(match.group(1))
                    total = int(match.group(2))
                    percent = int(finished / total * 100)
                    self.progress_signal.emit(percent)

            if not self._should_stop:
                self.log_signal.emit("<b style='color:green;'>运行完成！</b>")
            else:
                self.log_signal.emit("<b style='color:red;'>运行已终止！</b>")
        except Exception as e:
            self.log_signal.emit(f"<b style='color:red;'>执行失败：{str(e)}</b>")
        finally:
            if self._process and self._process.poll() is None:
                try:
                    self._process.terminate()
                except Exception:
                    pass
            self._process = None

    def stop(self):
        self._should_stop = True
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
            except Exception:
                pass


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
