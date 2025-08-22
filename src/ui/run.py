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
    QEvent,
    Qt,
    QTimer
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
                ("log", f"<b style='{STYLE_BASE} color:#a6e3ff;'>Run pytest</b>")
            )
            pytest.main(pytest_args, plugins=[plugin])
            q.put(
                ("log", f"<b style='{STYLE_BASE} color:#a6e3ff;'>Test completed ！</b>")
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
        self.case_path_label = StrongBodyLabel(self.display_case_path)
        apply_theme(self.case_path_label)
        self.case_path_label.setVisible(True)
        layout.addWidget(self.case_path_label)

        self.log_area = QTextEdit(self)
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(400)
        apply_theme(self.log_area)
        self.log_area.document().setMaximumBlockCount(2000)
        layout.addWidget(self.log_area, stretch=5)
        # 当前用例信息展示
        self.case_info_label = QLabel("Current case : ", self)
        apply_theme(self.case_info_label)
        layout.addWidget(self.case_info_label)
        self.process = QFrame(self)
        self.process.setFixedHeight(28)
        self.process.setStyleSheet(
            f"""
                    QFrame {{
                        background-color: rgba(255,255,255,0.06);
                        border: 1px solid rgba(255,255,255,0.12);
                        border-radius: 4px;
                        font-family: {FONT_FAMILY};
                    }}
                    """
        )
        layout.addWidget(self.process)
        # 填充条（作为背景动画层）
        self.process_fill = QFrame(self.process)
        self.process_fill.setGeometry(0, 0, 0, self.process.height())
        self.process_fill.setStyleSheet(
            """
            QFrame {
                background-color:  #001a4d;
                border-radius: 8px;
            }
            """
        )
        # 百分比文字（居中覆盖）
        self.process_label = QLabel("Process: 0%", self.process)
        self.process_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.process_label.setAlignment(Qt.AlignLeft)
        self.process_label.setAlignment(Qt.AlignVCenter)

        apply_theme(self.process_label)
        self.process_label.setStyleSheet(
            f"font-family: {FONT_FAMILY};"
        )
        self.process_label.resize(self.process.size())
        self.remaining_time_label = QLabel("Remaining : 00:00:00", self.process)
        self.remaining_time_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.remaining_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        apply_theme(self.remaining_time_label)
        self.remaining_time_label.setStyleSheet(f"font-family: {FONT_FAMILY};")
        self.remaining_time_label.resize(self.process.size())
        self.remaining_time_label.hide()
        self._remaining_seconds = 0
        self._remaining_time_timer = QTimer(self)
        self._remaining_time_timer.setInterval(1000)
        self._remaining_time_timer.timeout.connect(self._on_remaining_time_tick)
        self.process.installEventFilter(self)  # 让容器尺寸变化时同步 label/fill
        self._progress_animation = None
        self._current_percent = 0
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
        self._case_name_base = "Current case : "  # 基线文本，不含 fixture
        self._fixture_chain = []  # [(fixture_name, params), ...] 保序累积
        self._case_fn = ""  # 当前用例名（用于是否重置链）
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

    def eventFilter(self, obj, event):
        # 用 getattr 防止属性未创建时报 AttributeError；用 QEvent.Resize 做比较
        if obj is getattr(self, "process", None) and event.type() == QEvent.Resize:
            self.process_label.resize(self.process.size())
            self.remaining_time_label.resize(self.process.size())
            total_w = max(self.process.width(), 1)
            w = int(total_w * self._current_percent / 100)
            r = self.process.geometry()
            self.process_fill.setGeometry(0, 0, w, r.height())
        return super().eventFilter(obj, event)

    def _fixture_upsert(self, name: str, params: str):
        """按顺序 upsert：存在则更新参数，不存在则追加到末尾"""
        for i, (n, _) in enumerate(self._fixture_chain):
            if n == name:
                self._fixture_chain[i] = (name, params)
                break
        else:
            self._fixture_chain.append((name, params))
        self._rebuild_case_info_label()

    def _rebuild_case_info_label(self):
        """用基线 + 链式 fixture 重建 Current case 文本"""
        parts = [self._case_name_base.strip()]
        for n, p in self._fixture_chain:
            parts.append(f"{n}={p}")
        # 用竖线分隔，直观显示执行先后顺序
        self.case_info_label.setText(" | ".join(parts))

    def _append_log(self, msg: str):
        if msg.startswith("[PYQT_FIX]"):
            info = json.loads(msg[len("[PYQT_FIX]"):])
            name = str(info.get("fixture", "")).strip()
            params = str(info.get("params", "")).strip()
            if name and params:
                self._fixture_upsert(name, params)  # 累计或原位更新，不覆盖其它 fixture
            return
        if msg.startswith("[PYQT_CASE]"):
            fn = msg[len("[PYQT_CASE]"):].strip()
            if fn != self._case_fn:
                # 只有用例真的变化时才清空链
                self._case_fn = fn
                self._fixture_chain = []
            # 无论是否变化，都更新基线文本
            self._case_name_base = f"Current case : {fn}"
            self._rebuild_case_info_label()
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
        if not hasattr(self, "remaining_time_label"):
            return
        remaining_cases = max(self.total_count - self.finished_count, 0)
        remaining_ms = self.avg_case_duration * remaining_cases
        if remaining_cases <= 0 or remaining_ms <= 0:
            self._remaining_time_timer.stop()
            self.remaining_time_label.hide()
            self._remaining_seconds = 0
            return
        self._remaining_seconds = int(remaining_ms / 1000)
        h = self._remaining_seconds // 3600
        m = (self._remaining_seconds % 3600) // 60
        s = self._remaining_seconds % 60

        self.remaining_time_label.setText(
            f"Remaining : {h:02d}:{m:02d}:{s:02d}"
        )
        self.remaining_time_label.show()
        if not self._remaining_time_timer.isActive():
            self._remaining_time_timer.start()

    def _on_remaining_time_tick(self):
        if self._remaining_seconds <= 0:
            self._remaining_time_timer.stop()
            self.remaining_time_label.hide()
            return
        self._remaining_seconds -= 1
        h = self._remaining_seconds // 3600
        m = (self._remaining_seconds % 3600) // 60
        s = self._remaining_seconds % 60
        self.remaining_time_label.setText(
            f"Remaining : {h:02d}:{m:02d}:{s:02d}"
        )

    def update_progress(self, percent: int):
        # 归一化
        percent = max(0, min(100, int(percent)))
        self._current_percent = percent
        # 文本
        self.process_label.setText(f"Process: {percent}%")
        self.process_fill.setStyleSheet(
            '''QFrame { 
            background-color:  #001a4d; border-radius: 4px; 
            }'''
        )
        # 宽度动画
        total_w = self.process.width() or 300
        target_w = int(total_w * percent / 100)
        start_rect = self.process_fill.geometry()
        end_rect = QRect(0, 0, target_w, self.process.height())

        anim = QPropertyAnimation(self.process_fill, b"geometry")
        anim.setDuration(300)
        anim.setStartValue(start_rect)
        anim.setEndValue(end_rect)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._progress_animation = anim

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
        self.update_progress(0)
        self._remaining_time_timer.stop()
        self.remaining_time_label.hide()
        self._remaining_seconds = 0
        # —— 新一轮运行：重置 Current case 基线与链 ——
        self._case_fn = ""
        self._case_name_base = "Current case : "
        self._fixture_chain = []
        self.case_info_label.setText(self._case_name_base)
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
        self._remaining_time_timer.stop()
        self.remaining_time_label.hide()
        self._remaining_seconds = 0

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
        self._case_fn = ""
        self._case_name_base = "Current case : "
        self._fixture_chain = []
        self.case_info_label.setText(self._case_name_base)
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
