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
import multiprocessing
import queue
import os
import sip
# ui/run.py

from PyQt5.QtWidgets import QVBoxLayout, QTextEdit, QLabel, QFrame, QHBoxLayout
from qfluentwidgets import (
    CardWidget,
    StrongBodyLabel,
    PushButton,
    ProgressBar,
    InfoBar,
    InfoBarPosition,
    FluentIcon,
)
from PyQt5.QtCore import (
    QThread,
    pyqtSignal,
    QPropertyAnimation,
    QEasingCurve,
    QRect,
)
from PyQt5.QtGui import QTextCursor
import datetime
import re
import random
import sys
import time
from pathlib import Path
import traceback
import threading
import pytest
import io
import json
from contextlib import suppress
from src.util.constants import Paths, get_src_base
from src.util.pytest_redact import install_redactor_for_current_process
from .theme import apply_theme, STYLE_BASE, TEXT_COLOR, FONT_FAMILY
from .theme import format_log_html


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


def _pytest_worker(case_path: str, q: multiprocessing.Queue):
    """子进程执行pytest，将日志和进度写入队列"""
    pid = os.getpid()
    start_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        timestamp = datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
        timestamp = f"{timestamp}_{random.randint(1000, 9999)}"
        report_dir = (Path.cwd() / "report" / timestamp).resolve()
        report_dir.mkdir(parents=True, exist_ok=True)
        plugin = install_redactor_for_current_process()
        pytest_args = [
            "-v",
            "-s",
            "--full-trace",
            "--rootdir=.",
            "--import-mode=importlib",
            f"--resultpath={report_dir}",
            case_path,
        ]
        from src.tools.config_loader import load_config

        load_config(refresh=True)
        for m in list(sys.modules):
            if m.startswith("src.test"):
                sys.modules.pop(m, None)
        sys.modules.pop("src.tools.config_loader", None)
        sys.modules.pop("src.conftest", None)

        def emit_log(line: str):
            q.put(("log", line))
            match = re.search(r"\[PYQT_PROGRESS\]\s+(\d+)/(\d+)", line)
            if match:
                finished = int(match.group(1))
                total = int(match.group(2))
                percent = int(finished / total * 100)
                q.put(("progress", percent))

        writer = LiveLogWriter(emit_log)
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = writer

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
        try:
            q.put(
                ("log", f"<b style='{STYLE_BASE} color:green;'>Run pytest</b>")
            )
            pytest.main(pytest_args, plugins=[plugin])
            q.put(
                ("log", f"<b style='{STYLE_BASE} color:green;'>Test completed ！</b>")
            )
        finally:
            end_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for h in root_logger.handlers[:]:
                root_logger.removeHandler(h)
            for h in old_handlers:
                root_logger.addHandler(h)
            root_logger.setLevel(old_level)
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            writer.flush()
    except Exception as e:
        tb = traceback.format_exc()
        q.put(("log", f"<b style='{STYLE_BASE} color:red;'>Execution failed：{str(e)}</b>"))
        q.put(("log", f"<pre style='{STYLE_BASE} color:{TEXT_COLOR};'>{tb}</pre>"))


class CaseRunner(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, case_path: str, parent=None):
        super().__init__(parent)
        self.case_path = case_path
        self._should_stop = False
        self.old_handlers = []
        self.old_level = logging.NOTSET
        self._ctx = multiprocessing.get_context("spawn")
        self._queue: multiprocessing.Queue = self._ctx.Queue()
        self._proc: multiprocessing.Process | None = None
        self._case_start_time: float | None = None

    def run(self):
        """启动子进程运行pytest，并监听队列更新GUI"""
        logging.info("CaseRunner: preparing to start process for %s", self.case_path)
        self._proc = self._ctx.Process(
            target=_pytest_worker, args=(self.case_path, self._queue)
        )
        self._proc.start()
        logging.info(
            "CaseRunner: process started pid=%s for %s",
            self._proc.pid,
            self.case_path,
        )
        while True:
            if self._should_stop:
                if self._proc.is_alive():
                    self._proc.terminate()
                    self._proc.join()
                self.log_signal.emit("<b style='color:red;'>运行已终止！</b>")
                break
            # 主线程里定期检查_should_stop可实现停止功能
            try:
                kind, payload = self._queue.get(timeout=0.1)
                if kind == "log":
                    if payload.startswith("[PYQT_CASE]"):
                        self._case_start_time = time.time()
                    elif payload.startswith("[PYQT_PROGRESS]") and self._case_start_time is not None:
                        duration_ms = int((time.time() - self._case_start_time) * 1000)
                        self.log_signal.emit(f"[PYQT_CASETIME]{duration_ms}")
                        self._case_start_time = None
                    self.log_signal.emit(payload)
                elif kind == "progress":
                    self.progress_signal.emit(payload)
            except queue.Empty:
                pass
            if not self._proc.is_alive() and self._queue.empty():
                self.log_signal.emit(
                    f"<b style='color:gray;'>队列将关闭，进程存活：{self._proc.is_alive()}</b>"
                )
                logging.info("closing queue; proc alive=%s", self._proc.is_alive())
                break
        self._queue.close()
        self._queue.join_thread()
        self.log_signal.emit(
            f"<b style='color:gray;'>队列已关闭，进程存活：{self._proc.is_alive()}</b>"
        )

    def stop(self):
        # 设置标志位，run() 会检查该标志并自行退出
        self._should_stop = True
        if self._proc and self._proc.is_alive():
            self._proc.terminate()


class RunPage(CardWidget):
    """运行页"""

    def __init__(self, case_path, display_case_path=None, config=None, parent=None):
        super().__init__(parent)
        stack = getattr(parent, "stackedWidget", None)
        idx = stack.indexOf(self) if stack else None
        logging.info(
            "RunPage.__init__ start id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )
        self.setObjectName("runPage")
        apply_theme(self)
        self.case_path = case_path
        self.config = config
        self.main_window = parent  # 保存主窗口引用（用于InfoBar父窗口）

        self.display_case_path = self._calc_display_path(case_path, display_case_path)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        self.case_info_label = StrongBodyLabel(self.display_case_path)
        apply_theme(self.case_info_label)
        self.case_info_label.setVisible(True)
        layout.addWidget(self.case_info_label)

        self.progress = ProgressBar(self)
        self.progress.setValue(0)
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(self.progress, stretch=1)
        self.remaining_time_label = QLabel("", self)
        apply_theme(self.remaining_time_label)
        self.remaining_time_label.hide()
        progress_layout.addWidget(self.remaining_time_label)
        layout.addLayout(progress_layout)
        # 当前用例信息展示
        self.case_info_label = QLabel("", self)
        apply_theme(self.case_info_label)
        layout.addWidget(self.case_info_label)

        self.log_area = QTextEdit(self)
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(400)
        apply_theme(self.log_area)
        self.log_area.document().setMaximumBlockCount(2000)
        layout.addWidget(self.log_area, stretch=5)

        # 文本进度标签
        self.progress_text = QLabel("Process 0%", self)
        apply_theme(self.progress_text)
        layout.addWidget(self.progress_text)
        # 外部容器（透明）
        self.progress_container = QFrame(self)
        self.progress_container.setFixedHeight(10)
        self.progress_container.setStyleSheet(
            f"background: transparent;font-family: {FONT_FAMILY}; color:{TEXT_COLOR};"
        )
        layout.addWidget(self.progress_container)

        # 内部进度块
        self.progress_chunk = QFrame(self.progress_container)
        self.progress_chunk.setFixedHeight(10)
        self.progress_chunk.setStyleSheet(
            f"""
            background-color: #4a90e2;
            border-radius: 4px;
            font-family: {FONT_FAMILY};
            """
        )
        self.progress_chunk.setFixedWidth(0)
        self.action_btn = PushButton(self)
        if hasattr(self.action_btn, "setUseRippleEffect"):
            self.action_btn.setUseRippleEffect(True)
        if hasattr(self.action_btn, "setUseStateEffect"):
            self.action_btn.setUseStateEffect(True)
        self._set_action_button("stop")
        layout.addWidget(self.action_btn)
        self.setLayout(layout)
        self.finished_count = 0
        self.total_count = 0
        self.avg_case_duration = 0
        self._duration_sum = 0
        self._current_has_fixture = False
        stack = getattr(self.main_window, "stackedWidget", None)
        idx = stack.indexOf(self) if stack else None
        logging.info(
            "RunPage.__init__ end id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )

    def _append_log(self, msg: str):
        if msg.startswith("[PYQT_FIX]"):
            info = json.loads(msg[len("[PYQT_FIX]"):])
            base = self.case_info_label.text().split(" (", 1)[0]
            cur = self.case_info_label.text()
            params = info.get("params")
            if params:
                cur = (
                    f"{cur}, {info['fixture']}={params}"
                    if "(" in cur
                    else f"{base} ({info['fixture']}={params})"
                )
            self.case_info_label.setText(cur)
            return
        if msg.startswith("[PYQT_CASE]"):
            fn = msg[len("[PYQT_CASE]"):].strip()
            self.case_info_label.setText(fn)
            return
        if msg.startswith("[PYQT_CASEINFO]"):
            info = json.loads(msg[len("[PYQT_CASEINFO]"):])
            fixtures = info.get("fixtures") or []
            self._current_has_fixture = bool(fixtures)
            self._update_remaining_time_label()
            return
        if msg.startswith("[PYQT_CASETIME]"):
            try:
                duration_ms = int(msg[len("[PYQT_CASETIME]"):])
            except ValueError:
                return
            self.finished_count += 1
            self._duration_sum += duration_ms
            self.avg_case_duration = self._duration_sum / self.finished_count
            self._update_remaining_time_label()
            return
        if msg.startswith("[PYQT_PROGRESS]"):
            parts = msg[len("[PYQT_PROGRESS]"):].strip().split("/")
            if len(parts) == 2:
                with suppress(ValueError):
                    self.finished_count = int(parts[0])
                    self.total_count = int(parts[1])
            self._update_remaining_time_label()
            return
        html = format_log_html(msg)
        self.log_area.append(html)

        doc = self.log_area.document()
        if doc.blockCount() > 5000:
            cursor = QTextCursor(doc.firstBlock())
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _update_remaining_time_label(self):
        remaining_cases = max(self.total_count - self.finished_count, 0)
        remaining_ms = self.avg_case_duration * remaining_cases
        if not self._current_has_fixture or remaining_ms <= 0:
            self.remaining_time_label.hide()
            return
        remaining_sec = int(remaining_ms / 1000)
        h = remaining_sec // 3600
        m = (remaining_sec % 3600) // 60
        s = remaining_sec % 60
        self.remaining_time_label.setText(f"{h:02d}:{m:02d}:{s:02d}")
        self.remaining_time_label.show()

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
        start_rect = self.progress_chunk.geometry()
        end_rect = QRect(start_rect)
        end_rect.setWidth(progress_width)
        animation = QPropertyAnimation(self.progress_chunk, b"geometry")
        animation.setDuration(300)
        animation.setStartValue(start_rect)
        animation.setEndValue(end_rect)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start()
        self._progress_animation = animation

    def _set_action_button(self, mode: str):
        """根据模式设置操作按钮"""
        with suppress(TypeError):
            self.action_btn.clicked.disconnect()
        if mode == "run":
            text, icon, slot = "Run", FluentIcon.PLAY, self.run_case
        elif mode == "stop":
            text, icon, slot = "Stop", FluentIcon.CLOSE, self.on_stop
        else:
            raise ValueError(f"Unknown mode: {mode}")
        self.action_btn.setText(text)
        self.action_btn.setIcon(icon)
        self.action_btn.clicked.connect(lambda: logging.info("action_btn clicked"))
        self.action_btn.clicked.connect(slot)
        logging.info("Action button set to %s mode for RunPage id=%s", mode, id(self))

    def run_case(self):
        self.cleanup()
        self.log_area.clear()
        self.progress.setValue(0)
        self.update_progress(0)
        self._set_action_button("stop")
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
        stack = getattr(self.main_window, "stackedWidget", None)
        idx = stack.indexOf(self) if stack else None
        logging.info(
            "RunPage.cleanup start id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )
        runner = getattr(self, "runner", None)
        if not runner:
            return
        logging.info("runner isRunning before wait: %s", runner.isRunning())
        runner.stop()
        logging.getLogger().handlers[:] = runner.old_handlers
        logging.getLogger().setLevel(runner.old_level)
        logging.info(
            "before terminate: isRunning=%s threadId=%s",
            runner.isRunning(),
            int(runner.currentThreadId()),
        )
        elapsed = 0
        step = 500
        timeout = 5000
        while not runner.wait(step):
            elapsed += step
            if elapsed >= timeout:
                logging.warning(
                    "runner thread did not finish within %s ms", timeout
                )
                InfoBar.warning(
                    title="Warning",
                    content="线程未能及时结束",
                    parent=self.main_window,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                )
                break
            logging.info(
                "runner.isRunning after wait: %s", runner.isRunning()
            )
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
                logging.info("Disconnecting signals for RunPage id=%s", id(self))
                self.disconnect()
                logging.info("Signals disconnected for RunPage id=%s", id(self))
        stack = getattr(self.main_window, "stackedWidget", None)
        idx = stack.indexOf(self) if stack else None
        logging.info(
            "RunPage.cleanup end id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )

    def on_runner_finished(self):
        self.cleanup()
        self._set_action_button("run")
        self.action_btn.setEnabled(True)

    def on_stop(self):
        self._append_log("on_stop entered")
        self.cleanup()
        self._set_action_button("run")
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
