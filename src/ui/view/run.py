"""Run page UI view.

This module contains the view layer for the Run page:

- :class:`RunView` �?pure UI layout for logs, progress and controls.
- :class:`RunPage` �?lightweight widget that composes the view and
  delegates execution behaviour to :class:`src.ui.controller.run_ctl.CaseRunner`.
"""

from __future__ import annotations

from pathlib import Path
from contextlib import suppress
import logging
import json

from PyQt5.QtCore import QEvent, Qt, QTimer, QEasingCurve
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout
from qfluentwidgets import CardWidget, PushButton, StrongBodyLabel
from PyQt5 import sip

from src.util.constants import get_src_base
from src.ui.controller.run_ctl import CaseRunner
from src.ui.view.theme import ACCENT_COLOR, CONTROL_HEIGHT, FONT_FAMILY, apply_theme, format_log_html
from src.ui.view.common import animate_progress_fill, attach_view_to_page


class RunView(CardWidget):
    """Pure UI view for executing and monitoring test runs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        apply_theme(self)
        self.setObjectName("runView")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Header: case path
        self.case_path_label = StrongBodyLabel("", self)
        apply_theme(self.case_path_label)
        self.case_path_label.setStyleSheet(
            f"""
            StrongBodyLabel {{
                {('font-family:' + FONT_FAMILY + ';')}
            }}
            """
        )
        self.case_path_label.setVisible(True)
        layout.addWidget(self.case_path_label)

        # Log area
        self.log_area = QTextEdit(self)
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(400)
        apply_theme(self.log_area)
        layout.addWidget(self.log_area, stretch=5)

        # Current case info
        self.case_info_label = QLabel("Current case : ", self)
        apply_theme(self.case_info_label)
        self.case_info_label.setFixedHeight(CONTROL_HEIGHT)
        self.case_info_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.case_info_label.setStyleSheet(
            f"border-left: 4px solid {ACCENT_COLOR}; "
            f"padding-left: 8px; padding-top:0px; padding-bottom:0px; "
            f"font-family:{FONT_FAMILY};"
        )
        layout.addWidget(self.case_info_label)

        # Progress frame
        self.process = QFrame(self)
        self.process.setFixedHeight(CONTROL_HEIGHT)
        self.process.setStyleSheet(
            f"""
            QFrame {{
                background-color: rgba(255,255,255,0.06);
                border: 1px solid rgba(0,103,192,0.35);
                border-radius: 4px;
                font-family: {FONT_FAMILY};
            }}
            """
        )
        layout.addWidget(self.process)

        # Fill bar
        self.process_fill = QFrame(self.process)
        self.process_fill.setGeometry(0, 0, 0, CONTROL_HEIGHT)
        self.process_fill.setStyleSheet(
            f"QFrame {{ background-color: {ACCENT_COLOR}; border-radius: 4px; }}"
        )

        # Percent label (left)
        self.process_label = QLabel("Process: 0%", self.process)
        self.process_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.process_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        apply_theme(self.process_label)
        self.process_label.setStyleSheet(f"font-family: {FONT_FAMILY};")
        self.process_label.setGeometry(self.process.rect())

        # Remaining time (right)
        self.remaining_time_label = QLabel("Remaining : 00:00:00", self.process)
        self.remaining_time_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.remaining_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        apply_theme(self.remaining_time_label)
        self.remaining_time_label.setStyleSheet(f"font-family: {FONT_FAMILY};")
        self.remaining_time_label.setGeometry(self.process.rect())
        self.remaining_time_label.hide()

        # Action button
        self.action_btn = PushButton(self)
        self.action_btn.setObjectName("actionBtn")
        self.action_btn.setStyleSheet(
            f"""
            #actionBtn {{
                background-color: {ACCENT_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                height: {CONTROL_HEIGHT}px;
                font-family: {FONT_FAMILY};
                padding: 0 20px;
            }}
            #actionBtn:hover {{
                background-color: #0b5ea8;
            }}
            #actionBtn:pressed {{
                background-color: #084a85;
            }}
            #actionBtn:disabled {{
                background-color: rgba(0,103,192,0.35);
                color: rgba(255,255,255,0.6);
            }}
            """
        )
        if hasattr(self.action_btn, "setUseRippleEffect"):
            self.action_btn.setUseRippleEffect(True)
        if hasattr(self.action_btn, "setUseStateEffect"):
            self.action_btn.setUseStateEffect(True)
        self.action_btn.setFixedHeight(CONTROL_HEIGHT)
        layout.addWidget(self.action_btn)

        # Logical control map
        self.run_controls: dict[str, object] = {
            "run_main_header_case_label": self.case_path_label,
            "run_main_log_text": self.log_area,
            "run_main_case_info_label": self.case_info_label,
            "run_main_progress_frame": self.process,
            "run_main_progress_fill_frame": self.process_fill,
            "run_main_progress_percent_label": self.process_label,
            "run_main_remaining_label": self.remaining_time_label,
            "run_main_action_btn": self.action_btn,
        }


class RunPage(CardWidget):
    """Widget that hosts :class:`RunView` and drives test execution."""

    process: QFrame | None = None

    def __init__(self, case_path: str, display_case_path: str | None = None, config=None, parent=None):
        super().__init__(parent)
        self.setObjectName("runPage")
        apply_theme(self)

        self.case_path = case_path
        self.config = config
        self.main_window = parent

        self.display_case_path = self._calc_display_path(case_path, display_case_path)

        # Compose pure UI view and alias widgets for logic.
        self.view = RunView(self)
        attach_view_to_page(self, self.view)

        self.case_path_label: StrongBodyLabel = self.view.case_path_label
        self.case_path_label.setText(self.display_case_path)
        self.log_area: QTextEdit = self.view.log_area
        self.log_area.document().setMaximumBlockCount(2000)
        self.case_info_label: QLabel = self.view.case_info_label
        self.process: QFrame = self.view.process
        self.process_fill: QFrame = self.view.process_fill
        self.process_label: QLabel = self.view.process_label
        self.remaining_time_label: QLabel = self.view.remaining_time_label
        self.action_btn: PushButton = self.view.action_btn
        self.run_controls = self.view.run_controls

        # Remaining countdown: refresh every second.
        self._remaining_time_timer = QTimer(self)
        self._remaining_time_timer.setInterval(1000)
        self._remaining_time_timer.timeout.connect(self._on_remaining_tick)
        self._remaining_seconds = 0
        self._remaining_overtime = False
        self._overtime_seconds = 0
        self.process.installEventFilter(self)
        self._progress_animation = None
        self._current_percent = 0

        self.reset()
        self.finished_count = 0
        self.total_count = 0
        self.avg_case_duration = 0
        self._duration_sum = 0
        self._current_has_fixture = False

    def eventFilter(self, obj, event):  # type: ignore[override]
        if obj is self.process and event.type() == QEvent.Resize:
            rect = self.process.rect()
            self.process_label.setGeometry(rect)
            self.remaining_time_label.setGeometry(rect)
            total_w = max(rect.width(), 1)
            if self._current_percent >= 99:
                # Slightly overdraw to ensure the bar visually fills the frame.
                x = -1
                w = total_w + 2
            else:
                x = 0
                w = int(total_w * self._current_percent / 100)
            self.process_fill.setGeometry(x, 0, w, rect.height())
        return super().eventFilter(obj, event)

    def _fixture_upsert(self, name: str, params: str) -> None:
        for i, (n, _) in enumerate(self._fixture_chain):
            if n == name:
                self._fixture_chain[i] = (name, params)
                break
        else:
            self._fixture_chain.append((name, params))
        self._rebuild_case_info_label()

    def _rebuild_case_info_label(self) -> None:
        parts = [self._case_name_base.strip()]
        for n, p in self._fixture_chain:
            parts.append(f"{n}={p}")
        self.case_info_label.setText(" | ".join(parts))

    def _append_log(self, msg: str) -> None:
        if "libpng warning: iCCP: known incorrect sRGB profile" in msg:
            return
        if msg.strip() == "KeyboardInterrupt":
            return
        # Extract raw PYQT markers from log lines that include timestamps/prefixes.
        marker_index = msg.find("[PYQT_")
        marker = msg[marker_index:] if marker_index != -1 else msg

        if marker.startswith("[PYQT_FIX]"):
            info = json.loads(marker[len("[PYQT_FIX]") :])
            name = str(info.get("fixture", "")).strip()
            params = str(info.get("params", "")).strip()
            if name and params:
                self._fixture_upsert(name, params)
            return
        if marker.startswith("[PYQT_CASE]"):
            fn = marker[len("[PYQT_CASE]") :].strip()
            if fn != getattr(self, "_case_fn", ""):
                self._case_fn = fn
                self._fixture_chain = []
            self._case_name_base = f"Current case : {fn}"
            self._rebuild_case_info_label()
            return
        if marker.startswith("[PYQT_CASEINFO]"):
            info = json.loads(marker[len("[PYQT_CASEINFO]") :])
            fixtures = info.get("fixtures") or []
            self._current_has_fixture = bool(fixtures)
            self._update_remaining_time_label()
            return
        if marker.startswith("[PYQT_CASETIME]"):
            try:
                duration_ms = int(marker[len("[PYQT_CASETIME]") :])
            except ValueError:
                return
            self.finished_count += 1
            self._duration_sum += duration_ms
            self.avg_case_duration = self._duration_sum / self.finished_count
            self._update_remaining_time_label()
            return
        if marker.startswith("[PYQT_PROGRESS]"):
            parts = marker[len("[PYQT_PROGRESS]") :].strip().split("/")
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

    def _format_hms(self, seconds: int) -> str:
        s = max(0, int(seconds))
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        return f"Remaining : {h:02d}:{m:02d}:{sec:02d}"

    def _start_remaining_timer(self, seconds: int) -> None:
        if seconds <= 0:
            return
        self._remaining_seconds = seconds
        self.remaining_time_label.setText(self._format_hms(self._remaining_seconds))
        self.remaining_time_label.show()
        if not self._remaining_time_timer.isActive():
            self._remaining_time_timer.start()

    def _stop_remaining_timer(self) -> None:
        self._remaining_time_timer.stop()
        self._remaining_overtime = False
        self._overtime_seconds = 0
        self.remaining_time_label.hide()

    def _on_remaining_tick(self) -> None:
        if self._remaining_overtime:
            self._overtime_seconds += 1
            self.remaining_time_label.setText(
                f"Overtime : {self._format_hms(self._overtime_seconds)[12:]}"
            )
            return

        self._remaining_seconds -= 1
        if self._remaining_seconds <= 0:
            remaining_cases = max(self.total_count - self.finished_count, 0)
            runner_running = self.runner is not None and self.runner.isRunning()
            if remaining_cases > 0 or runner_running:
                self._remaining_overtime = True
                self._overtime_seconds = 0
                self.remaining_time_label.setText("Overtime : 00:00:00")
                self.remaining_time_label.show()
                return
            self._stop_remaining_timer()
            return

        self.remaining_time_label.setText(self._format_hms(self._remaining_seconds))

    def _update_remaining_time_label(self) -> None:
        remaining_cases = max(self.total_count - self.finished_count, 0)
        if remaining_cases <= 0:
            self._stop_remaining_timer()
            return

        remaining_ms = self.avg_case_duration * remaining_cases
        seconds = int(remaining_ms // 1000) if remaining_ms > 0 else -1
        if seconds > 0:
            self._start_remaining_timer(seconds)
            return

        if not self._remaining_time_timer.isActive() and not self._remaining_overtime:
            pass

    def update_progress(self, percent: int) -> None:
        percent = max(0, min(100, int(percent)))
        self._current_percent = percent
        self.process_label.setText(f"Process: {percent}%")
        color = ACCENT_COLOR
        self.process_fill.setStyleSheet(
            f"QFrame {{ background-color: {color}; border-radius: 4px; }}"
        )
        anim = animate_progress_fill(self.process_fill, self.process, percent)
        if anim is not None:
            self._progress_animation = anim

    def _trigger_config_run(self) -> None:
        self.main_window.caseConfigPage.config_ctl.on_run()

    def _set_action_button(self, mode: str) -> None:
        with suppress(TypeError):
            self.action_btn.clicked.disconnect()
        if mode == "run":
            text, slot = "Run", self._trigger_config_run
        elif mode == "stop":
            text, slot = "Stop", self.on_stop
        else:
            raise ValueError(f"Unknown mode: {mode}")
        self.action_btn.setText(text)
        self.action_btn.clicked.connect(lambda: logging.info("action_btn clicked"))
        self.action_btn.clicked.connect(slot)
        logging.info("Action button set to %s mode for RunPage id=%s", mode, id(self))

    def reset(self) -> None:
        with suppress(Exception):
            self.cleanup()
        self.log_area.clear()
        self.update_progress(0)
        self.remaining_time_label.hide()
        self._stop_remaining_timer()
        self._case_fn = ""
        self._case_name_base = "Current case : "
        self._fixture_chain: list[tuple[str, str]] = []
        self.case_info_label.setText(self._case_name_base)
        self._set_action_button("run")
        self.action_btn.setEnabled(True)

    def run_case(self) -> None:
        self.reset()
        self._set_action_button("stop")
        account_name = ""
        if self.main_window and self.main_window._active_account:
            account_name = str(self.main_window._active_account.get("username", "")).strip()
        self.runner = CaseRunner(self.case_path, account_name=account_name, display_case_path=self.display_case_path)
        self.runner.log_signal.connect(self._append_log)
        self.runner.progress_signal.connect(self.update_progress)
        with suppress(Exception):
            self.runner.report_dir_signal.connect(self._on_report_dir_ready)
        self.runner.finished.connect(self._finalize_runner)
        self.runner.start()

    def _finalize_runner(self) -> None:
        runner = self.runner
        if runner is None:
            return
        for signal, slot in (
            (runner.log_signal, self._append_log),
            (runner.progress_signal, self.update_progress),
        ):
            with suppress((TypeError, RuntimeError)):
                signal.disconnect(slot)
        with suppress((TypeError, RuntimeError)):
            runner.report_dir_signal.disconnect(self._on_report_dir_ready)
        with suppress((TypeError, RuntimeError)):
            runner.finished.disconnect(self._finalize_runner)
        runner.deleteLater()
        self.runner = None
        self.on_runner_finished()

    def _on_report_dir_ready(self, path: str) -> None:
        self.main_window.enable_report_page(path)

    def cleanup(self, disconnect_page: bool = True) -> None:
        stack = self.main_window.stackedWidget
        idx = stack.indexOf(self)
        logging.info(
            "RunPage.cleanup start id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )
        self.remaining_time_label.hide()
        runner = self.runner
        if runner is None:
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
            QApplication.processEvents()
            elapsed += step
            if elapsed >= timeout:
                logging.warning("runner thread did not finish within %s ms", timeout)
                break
            logging.info("runner.isRunning after wait: %s", runner.isRunning())
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
        stack = self.main_window.stackedWidget
        idx = stack.indexOf(self)
        logging.info(
            "RunPage.cleanup end id=%s isdeleted=%s index=%s",
            id(self),
            sip.isdeleted(self),
            idx,
        )

    def on_runner_finished(self) -> None:
        self.cleanup()
        self._stop_remaining_timer()
        self._set_action_button("run")
        self.action_btn.setEnabled(True)
        self._case_fn = ""
        self._case_name_base = "Current case : "
        self._fixture_chain = []
        self.case_info_label.setText(self._case_name_base)

    def on_stop(self) -> None:
        self._append_log("on_stop entered")
        self.cleanup()
        self._stop_remaining_timer()
        self._set_action_button("run")
        self.action_btn.setEnabled(True)

    def _get_application_base(self) -> Path:
        return Path(get_src_base()).resolve()

    def _calc_display_path(self, case_path: str, display_case_path: str | None) -> str:
        if display_case_path:
            p = Path(display_case_path)
            if ".." not in p.parts and not p.drive and not p.is_absolute():
                return display_case_path.replace("\\", "/")
        app_base = self._get_application_base()
        display_case_path = Path(case_path).resolve()
        from contextlib import suppress as _s

        with _s(ValueError):
            display_case_path = display_case_path.relative_to(app_base)
        return display_case_path.as_posix()


__all__ = ["RunView", "RunPage"]
