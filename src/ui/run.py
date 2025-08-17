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
from pathlib import Path
import traceback
import threading
import pytest
import io
from contextlib import suppress
from src.util.constants import get_src_base
from src.util.pytest_redact import install_redactor_for_current_process
from src.util.decorators import lazy_proerty


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
        logging.info(
            "_pytest_worker start pid=%s time=%s case_path=%s",
            pid,
            start_ts,
            case_path,
        )
        try:
            q.put(("log", "<b style='color:blue;'>开始执行pytest</b>"))
            pytest.main(pytest_args, plugins=[plugin])
            q.put(("log", "<b style='color:green;'>运行完成！</b>"))
        finally:
            end_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info(
                "_pytest_worker end pid=%s time=%s case_path=%s",
                pid,
                end_ts,
                case_path,
            )
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
        q.put(("log", f"<b style='color:red;'>执行失败：{str(e)}</b>"))
        q.put(("log", f"<pre>{tb}</pre>"))


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
        self.stack = getattr(parent, "stackedWidget", None)
        idx = self.stack.indexOf(self) if self.stack else None
        logging.info(
            "RunPage.__init__ start id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )
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
        self.log_area.setStyleSheet(
            "font-size:16px; background:#2b2b2b; color:#fafafa;font-family: Verdana;"
        )
        self.log_area.document().setMaximumBlockCount(2000)
        layout.addWidget(self.log_area, stretch=5)

        # 文本进度标签
        self.progress_text = QLabel("Process 0%", self)
        self.progress_text.setStyleSheet(
            "font-size: 14px; background:#2b2b2b; color:#fafafa;font-family: Verdana;"
        )
        layout.addWidget(self.progress_text)
        # 外部容器（透明）
        self.progress_container = QFrame(self)
        self.progress_container.setFixedHeight(10)
        self.progress_container.setStyleSheet("background: transparent;font-family: Verdana;")
        layout.addWidget(self.progress_container)

        # 内部进度块
        self.progress_chunk = QFrame(self.progress_container)
        self.progress_chunk.setFixedHeight(10)
        self.progress_chunk.setStyleSheet(
            """
            background-color: #4a90e2;
            border-radius: 4px;
            font-family: Verdana;
            """
        )
        self.progress_chunk.setFixedWidth(0)
        self.action_btn = PushButton("Exit", self)
        self.action_btn.setIcon(FluentIcon.CLOSE)
        if hasattr(self.action_btn, "setUseRippleEffect"):
            self.action_btn.setUseRippleEffect(True)
        if hasattr(self.action_btn, "setUseStateEffect"):
            self.action_btn.setUseStateEffect(True)
        self._setup_action_btn("Exit", FluentIcon.CLOSE, self.on_stop)
        layout.addWidget(self.action_btn)
        self.setLayout(layout)
        idx = self.stack.indexOf(self) if self.stack else None
        logging.info(
            "RunPage.__init__ end id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )

    def _log_action(self):
        logging.info("action_btn clicked")

    def _setup_action_btn(self, text: str, icon: FluentIcon, handler):
        """统一配置 action_btn，减少重复代码"""
        self.action_btn.setText(text)
        self.action_btn.setIcon(icon)
        with suppress(TypeError):
            self.action_btn.clicked.disconnect()
        self.action_btn.clicked.connect(self._log_action)
        self.action_btn.clicked.connect(handler)
        logging.info(
            "action_btn configured to %s for RunPage id=%s",
            getattr(handler, "__name__", str(handler)),
            id(self),
        )

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

    def run_case(self):
        self.cleanup()
        self.log_area.clear()
        self.progress.setValue(0)
        self.update_progress(0)

        self._setup_action_btn("Exit", FluentIcon.CLOSE, self.on_stop)
        self.runner = CaseRunner(self.case_path)
        self.runner.log_signal.connect(self._append_log)
        self.runner.progress_signal.connect(self.update_progress)
        self.runner.finished.connect(self.on_runner_finished)
        self.runner.start()


    def cleanup(self, disconnect_page: bool = True):
        idx = self.stack.indexOf(self) if self.stack else None
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
        idx = self.stack.indexOf(self) if self.stack else None
        logging.info(
            "RunPage.cleanup end id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )

    def on_runner_finished(self):
        runner = getattr(self, "runner", None)
        if runner:
            for signal, slot in (
                (runner.log_signal, self._append_log),
                (runner.progress_signal, self.update_progress),
            ):
                with suppress((TypeError, RuntimeError)):
                    signal.disconnect(slot)
            with suppress((TypeError, RuntimeError)):
                runner.finished.disconnect(self.on_runner_finished)
            runner.deleteLater()
            self.runner = None
        self._setup_action_btn("Test", FluentIcon.PLAY, self.run_case)
        self.action_btn.setEnabled(True)

    def on_stop(self):
        self._append_log("on_stop entered")
        self.cleanup()
        self._setup_action_btn("Test", FluentIcon.PLAY, self.run_case)
        self.action_btn.setEnabled(True)

    @lazy_proerty
    def app_base(self) -> Path:
        """应用根路径（懒加载）"""
        return Path(get_src_base()).resolve()

    def _calc_display_path(self, case_path: str, display_case_path: str | None) -> str:
        """计算用于显示的用例路径"""
        if display_case_path:
            p = Path(display_case_path)
            if ".." not in p.parts and not p.drive and not p.is_absolute():
                return display_case_path.replace("\\", "/")
        display_case_path = Path(case_path).resolve()
        with suppress(ValueError):
            display_case_path = display_case_path.relative_to(self.app_base)
        return display_case_path.as_posix()
