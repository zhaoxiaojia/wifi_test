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

import datetime
import os
import random
import re
import subprocess
import sys
import traceback
from contextlib import suppress
from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QFrame, QLabel, QTextEdit, QVBoxLayout
from qfluentwidgets import (
    CardWidget,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    ProgressBar,
    PushButton,
    StrongBodyLabel,
)

from src.util.constants import get_src_base


class CaseRunner(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, case_path: str, parent=None):
        super().__init__(parent)
        self.case_path = case_path
        self._should_stop = False
        self._proc: subprocess.Popen | None = None

    def run(self):
        logging.info("CaseRunner start tid=%s", int(QThread.currentThreadId()))
        code = None
        try:
            timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
            timestamp = f"{timestamp}_{random.randint(1000, 9999)}"
            report_dir = (Path.cwd() / "report" / timestamp).resolve()
            report_dir.mkdir(parents=True, exist_ok=True)

            from src.tools.config_loader import load_config

            load_config(refresh=True)

            if getattr(sys, "frozen", False):  # 打包环境
                python_path = Path(sys.executable).with_name("pythonw.exe")
            else:
                python_path = sys.executable

            cmd = [
                python_path,
                "-m",
                "pytest",
                "-v",
                "-s",
                "--full-trace",
                "--rootdir=.",
                "--import-mode=importlib",
                f"--resultpath={report_dir}",
                self.case_path,
            ]

            kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "bufsize": 1,
            }
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            self._proc = subprocess.Popen(cmd, **kwargs)

            for line in self._proc.stdout:
                line = line.rstrip()
                self.log_signal.emit(line)
                match = re.search(r"\[PYQT_PROGRESS\]\s+(\d+)/(\d+)", line)
                if match:
                    finished = int(match.group(1))
                    total = int(match.group(2))
                    percent = int(finished / total * 100)
                    self.progress_signal.emit(percent)
                if self._should_stop:
                    break

            with suppress(Exception):
                self._proc.stdout.close()
            code = self._proc.wait()

            if self._should_stop:
                self.log_signal.emit("<b style='color:red;'>运行已终止！</b>")
            else:
                self.log_signal.emit("<b style='color:green;'>运行完成！</b>")
        except Exception as e:
            tb = traceback.format_exc()
            self.log_signal.emit(f"<b style='color:red;'>执行失败：{str(e)}</b>")
            self.log_signal.emit(f"<pre>{tb}</pre>")
        finally:
            if self._proc and self._proc.poll() is None:
                with suppress(Exception):
                    self._proc.kill()
            logging.info(
                "CaseRunner end tid=%s code=%s",
                int(QThread.currentThreadId()),
                code,
            )

    def stop(self):
        self._should_stop = True
        logging.info("stop called: isRunning=%s", self.isRunning())
        if self._proc and self._proc.poll() is None:
            with suppress(Exception):
                self._proc.terminate()

class RunPage(CardWidget):
    """运行页"""

    def __init__(self, case_path, display_case_path=None, config=None, parent=None):
        super().__init__(parent)
        self.setObjectName("runPage")
        self.case_path = case_path
        self.config = config
        self.main_window = parent  # 保存主窗口引用（用于InfoBar父窗口）

        self.display_case_path = self._calc_display_path(case_path, display_case_path)

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
        self.action_btn = PushButton("Exit", self)
        self.action_btn.setIcon(FluentIcon.CLOSE)
        self.action_btn.clicked.connect(self.on_stop)
        layout.addWidget(self.action_btn)
        self.setLayout(layout)

    def _append_log(self, msg: str):
        upper_msg = msg.upper()
        colors = {"ERROR": "red", "WARNING": "orange", "INFO": "blue"}
        color = next((c for k, c in colors.items() if k in upper_msg), None)
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
        self.progress_text.setText(f"Process :  {percent}%")
        total_width = self.progress_container.width() or 300  # 默认宽度
        progress_width = int(total_width * percent / 100)
        # 更新进度块宽度
        self.progress_chunk.setFixedWidth(progress_width)

    def run_case(self):
        self.cleanup()
        self.log_area.clear()
        self.progress.setValue(0)
        self.update_progress(0)

        self.action_btn.setText("Exit")
        self.action_btn.setIcon(FluentIcon.CLOSE)
        with suppress(TypeError):
            self.action_btn.clicked.disconnect()
        self.action_btn.clicked.connect(self.on_stop)
        self.runner = CaseRunner(self.case_path)
        self.runner.log_signal.connect(self._append_log)
        self.runner.progress_signal.connect(self.update_progress)
        # 关键修改：InfoBar的父窗口改为主窗口（而非RunPage自身）
        # self.runner.finished.connect(
        #     lambda: InfoBar.success(
        #         title="Done",
        #         content="Test Done",
        #         parent=self.main_window,  # 这里改为主窗口
        #         position=InfoBarPosition.TOP,
        #         duration=1800,
        #     )
        # )
        self.runner.finished.connect(self._finalize_runner)
        self.runner.start()

    def _finalize_runner(self):
        runner = getattr(self, "runner", None)
        if not runner:
            self.on_runner_finished()
            return
        for signal, slot in (
                (runner.log_signal, self._append_log),
                (runner.progress_signal, self.update_progress),
        ):
            with suppress((TypeError, RuntimeError)):
                signal.disconnect(slot)
        with suppress((TypeError, RuntimeError)):
            runner.finished.disconnect(self._finalize_runner)
        runner.deleteLater()
        self.runner = None
        self.on_runner_finished()

    def cleanup(self, disconnect_page: bool = True):
        runner = getattr(self, "runner", None)
        logging.info(
            "cleanup start tid=%s runner=%s",
            int(QThread.currentThreadId()),
            runner,
        )
        if not runner:
            logging.info("cleanup end wait=%s", None)
            return None
        runner.stop()
        logging.info("runner isRunning before first wait: %s", runner.isRunning())
        finished = runner.wait(3000)
        logging.info(
            "runner.wait(3000) after stop returned %s; isRunning=%s",
            finished,
            runner.isRunning(),
        )
        if not finished:
            logging.warning("runner thread did not stop gracefully within 3000 ms, terminating")
            runner.terminate()
            finished = runner.wait(3000)
            logging.info(
                "runner.wait(3000) after terminate returned %s; isRunning=%s",
                finished,
                runner.isRunning(),
            )
            if not finished:
                logging.error("runner thread did not terminate within 3000 ms")
        for signal, slot in (
                (runner.log_signal, self._append_log),
                (runner.progress_signal, self.update_progress),
        ):
            with suppress((TypeError, RuntimeError)):
                signal.disconnect(slot)
        with suppress((TypeError, RuntimeError)):
            runner.finished.disconnect(self.on_runner_finished)
        self.runner = None
        if disconnect_page:
            with suppress(TypeError):
                self.disconnect()
        logging.info("cleanup end wait=%s", finished)
        return finished

    def on_runner_finished(self):
        logging.info("runner finished signal received")
        self.cleanup()
        self.action_btn.setText("Test")
        self.action_btn.setIcon(FluentIcon.PLAY)
        with suppress(TypeError):
            self.action_btn.clicked.disconnect()
        self.action_btn.clicked.connect(self.run_case)
        self.action_btn.setEnabled(True)

    def on_stop(self):
        runner = getattr(self, "runner", None)
        logging.info(
            "cleanup start tid=%s runner=%s",
            int(QThread.currentThreadId()),
            runner,
        )
        finished = self.cleanup()
        logging.info("cleanup finished wait=%s", finished)
        self.action_btn.setText("Test")
        self.action_btn.setIcon(FluentIcon.PLAY)
        with suppress(TypeError):
            self.action_btn.clicked.disconnect()
        self.action_btn.clicked.connect(self.run_case)
        self.action_btn.setEnabled(True)

    def _get_application_base(self) -> Path:
        """获取应用根路径"""
        return Path(get_src_base()).resolve()

    def _calc_display_path(self, case_path: str, display_case_path: str | None) -> str:
        """计算用于显示的用例路径"""
        if display_case_path:
            p = Path(display_case_path)
            if ".." not in p.parts and not p.drive and not p.is_absolute():
                return display_case_path.replace("\\", "/")
        app_base = self._get_application_base()
        display_case_path = Path(case_path).resolve()
        with suppress(ValueError):
            display_case_path = display_case_path.relative_to(app_base)
        return display_case_path.as_posix()
