"""Run page UI view.

This module contains the view layer for the Run page:

- :class:`RunView` �?pure UI layout for logs, progress and controls.
- :class:`RunPage` �?lightweight widget that composes the view and
  delegates execution behaviour to :class:`src.ui.controller.run_ctl.CaseRunner`.
"""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path
from contextlib import suppress
import logging
import json

from PyQt5.QtCore import QEvent, Qt, QTimer, QEasingCurve, QUrl, QPoint, QSize
from PyQt5.QtGui import QTextCursor, QDesktopServices, QIcon
from PyQt5.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout
from qfluentwidgets import CardWidget, PushButton, StrongBodyLabel
from PyQt5 import sip

from src.util.constants import get_src_base, Paths
from src.ui.controller.run_ctl import CaseRunner, ExcelPlanRunner
from src.ui.view.theme import ACCENT_COLOR, CONTROL_HEIGHT, FONT_FAMILY, apply_theme, format_log_html
from src.ui.view.common import animate_progress_fill, attach_view_to_page
from qfluentwidgets import MessageBox
from src.util.constants import get_config_base


def _is_project_test_script(case_path: str) -> bool:
    """判断是否为 project/ 下的功能测试脚本"""
    p = Path(case_path).resolve()
    parts = p.parts

    # 查找连续的三个部分：'src', 'test', 'project'
    for i in range(len(parts) - 2):
        if (str(parts[i]).lower() == "src" and
                str(parts[i + 1]).lower() == "test" and
                str(parts[i + 2]).lower() == "project"):
            return True
    return False

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

        # Floating button (bottom-right of log area) to open the
        # Allure HTML report for the latest run. Enabled only after a
        # test run has finished and the report directory is known.
        self.open_allure_btn = PushButton(self.log_area)
        self.open_allure_btn.setObjectName("openAllureBtn")
        self.open_allure_btn.setText("")
        self.open_allure_btn.setToolTip("Open Allure report")
        self.open_allure_btn.setFixedSize(32, 32)
        self.open_allure_btn.setEnabled(False)
        self.open_allure_btn.setStyleSheet(
            """
            #openAllureBtn {
                border-radius: 16px;
                background-color: #555555;
                border: none;
                color: white;
                font-size: 16px;
            }
            #openAllureBtn:hover {
                background-color: #666666;
            }
            #openAllureBtn:pressed {
                background-color: #444444;
            }
            #openAllureBtn:disabled {
                background-color: rgba(255,255,255,0.15);
            }
            """
        )
        # Use a Google Chrome icon from the shared res directory when available.
        icon_path = Path(Paths.RES_DIR) / "logo" / "google-chrome.webp"
        if icon_path.exists():
            self.open_allure_btn.setIcon(QIcon(str(icon_path)))
            self.open_allure_btn.setIconSize(QSize(20, 20))
        else:
            self.open_allure_btn.setText("🌐")
        self._allure_report_dir: str | None = None
        self._allure_server_proc: subprocess.Popen | None = None
        self._allure_server_url: str | None = None
        self.open_allure_btn.clicked.connect(self._on_open_allure_clicked)

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

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._position_allure_button()

    def _position_allure_button(self) -> None:
        if not self.open_allure_btn:
            return
        margin_right = 20
        margin_bottom = 12
        rect = self.log_area.rect()
        x = rect.right() - self.open_allure_btn.width() - margin_right
        y = rect.bottom() - self.open_allure_btn.height() - margin_bottom
        self.open_allure_btn.move(x, y)

    def set_allure_report_dir(self, report_dir: str | None) -> None:
        self._allure_report_dir = report_dir
        self.open_allure_btn.setEnabled(bool(report_dir))

    def _on_open_allure_clicked(self) -> None:
        if not self._allure_report_dir:
            return
        base = Path(self._allure_report_dir)
        report_root = (base / "allure-report").resolve()
        index_path = report_root / "index.html"
        if not report_root.exists() or not index_path.exists():
            return

        if self._allure_server_proc is not None and self._allure_server_proc.poll() is None and self._allure_server_url:
            QDesktopServices.openUrl(QUrl(self._allure_server_url))
            return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
            cwd=str(report_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._allure_server_proc = proc
        self._allure_server_url = f"http://127.0.0.1:{port}/index.html"
        QDesktopServices.openUrl(QUrl(self._allure_server_url))


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
        self.excel_plan_path: str | None = None #260104 For function test;
        self._last_report_dir: str | None = None
        self._user_cancelled_single_run = False ##260105 For function test;

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

        #260105 For function test; Auto-load last function plan
        try:
            from src.util.constants import get_config_base
            context_file = get_config_base() / "last_function_plan.txt"
            print(f"[DEBUG] Looking for last plan at: {context_file}")
            try:
                with open(context_file, 'r', encoding='utf-8') as f:
                    excel_path = f.read().strip()
                # ↑↑↑ 文件 f 在此处已明确超出作用域并应被关闭 ↑↑↑
            except Exception as read_error:
                print(f"[ERROR] Failed to read last_function_plan.txt: {read_error}")
                excel_path = None

                # --- Step 2: 验证并设置路径 ---
            if excel_path and Path(excel_path).exists():
                print(f"[DEBUG] Found plan path in file: '{excel_path}'")
                print(f"[DEBUG] Plan file exists on disk. Setting it.")
                self.set_excel_plan_path(excel_path)

                # --- Step 3: 尝试删除（增加安全措施）---
                try:
                    # 可选：增加一个极短的延迟，让 OS 有时间释放句柄
                    import time
                    time.sleep(0.01)  # 10毫秒，通常足够

                    context_file.unlink()
                    print(f"[DEBUG] Deleted last_function_plan.txt in __init__ for safety.")

                except PermissionError as pe:
                    # 捕获特定的权限错误
                    print(f"[WARNING] Permission denied when deleting file: {pe}")
                    # 降级方案：重命名文件
                    try:
                        bak_file = context_file.with_suffix('.txt.bak')
                        if bak_file.exists():
                            bak_file.unlink()  # 先清理旧的 .bak
                        context_file.rename(bak_file)
                        print(f"[DEBUG] Renamed to {bak_file.name} as fallback.")
                    except Exception as rename_error:
                        print(f"[ERROR] Fallback rename also failed: {rename_error}")

                except Exception as e:
                    print(f"[WARNING] Unexpected error when deleting file: {e}")
        except Exception as e:
            print(f"[DEBUG] Warning: Could not auto-load last function plan: {e}")
        # End of auto-load block

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
        print(f"[DEBUG] run_case() called.")
        print(f"[DEBUG] Current state - case_path: '{self.case_path}', excel_plan_path: '{self.excel_plan_path}'")

        self.reset()
        self._set_action_button("stop")
        account_name = ""
        if self.main_window and self.main_window._active_account:
            account_name = str(self.main_window._active_account.get("username", "")).strip()

        # --- 新增：智能判断是否应运行 Excel 计划 ---
        # --- 新增：只有 project 测试才允许使用 ExcelPlanRunner ---
        is_project_case = _is_project_test_script(self.case_path)
        # 如果不是 project 测试，强制清除 excel_plan_path
        if not is_project_case:
            self.excel_plan_path = None
            print("[DEBUG] Non-project test detected. Cleared excel_plan_path.")

        # 条件2: excel_plan_path 尚未被设置 (即为 None)
        is_excel_not_set = self.excel_plan_path is None

        if is_project_case and self.excel_plan_path is None:
            try:
                #app_base = self._get_application_base()
                #last_plan_file = app_base / "dist" / "last_function_plan.txt"
                last_plan_file = get_config_base() / "last_function_plan.txt"

                if last_plan_file.exists():
                    excel_path = None
                    # --- Step 1: 仅读取内容，确保 with 块独立结束 ---
                    with open(last_plan_file, 'r', encoding='utf-8') as f:
                        excel_path = f.read().strip()
                    # ↑↑↑ 文件 f 在此处已明确关闭 ↑↑↑

                    # --- Step 2: 验证路径并设置 ---
                    if excel_path and Path(excel_path).exists():
                        self.set_excel_plan_path(excel_path)
                        print(f"[DEBUG] Auto-switched to Excel plan: {excel_path}")

                        # --- Step 3: 尝试删除（关键修复）---
                        try:
                            import time
                            time.sleep(0.01)  # 增加10毫秒延迟，让OS释放句柄

                            last_plan_file.unlink()
                            print(f"[DEBUG] Deleted last_function_plan.txt for safety.")

                        except PermissionError:
                            # --- 降级策略：重命名文件 ---
                            try:
                                bak_path = last_plan_file.with_suffix('.txt.bak')
                                if bak_path.exists():
                                    bak_path.unlink()  # 清理旧备份
                                last_plan_file.rename(bak_path)
                                print(f"[DEBUG] Renamed to {bak_path.name} as fallback.")
                            except Exception as rename_e:
                                print(f"[ERROR] Rename fallback failed: {rename_e}")

                        except Exception as delete_error:
                            print(f"[WARNING] Unexpected delete error: {delete_error}")

            except Exception as e:
                print(f"[DEBUG] Warning: Failed to auto-switch to Excel plan: {e}")

            print(f"[DEBUG] Current state - case_path: '{self.case_path}', excel_plan_path: '{self.excel_plan_path}'")

            # --- 260105 新增：弹出提醒对话框（仅当在 project/ 下且未加载到计划时）---
            # 判断当前 case 是否属于 project 目录
            is_project_case = _is_project_test_script(self.case_path)
            # 判断是否成功加载了 Excel 计划
            has_excel_plan = self.excel_plan_path is not None and self.excel_plan_path != "None"
            print(f"[DEBUG] is_project_case check: 'project' in {Path(self.case_path).parts} -> {is_project_case}")

            if is_project_case and not has_excel_plan:
                from qfluentwidgets import MessageBox

                # 创建消息框
                message_box = MessageBox(
                    title="Single Function Script Test Mode",
                    content="Do Not Find Function Test Suite File,\n\n"
                            "Single Function Script Will Start.\n\n"
                            "Continue? \n\n"
                            "If Not, Please Stop This test and Choice Test Scripts In Advanced Config UI",
                    parent=self.main_window  # 使用主窗口作为父窗口
                )
                message_box.yesButton.setText("Continue?")
                #message_box.cancelButton.setText("Cancel?")
                message_box.cancelButton.hide()

                # # 显示对话框并等待用户选择
                # if not message_box.exec():
                #     # 用户点击了“取消”
                #     print("[INFO] User cancelled single-script run.")
                #     # 可以在这里添加取消后的逻辑，例如：
                #     #self.close() # 关闭当前页面 (可选)
                #     #self._user_cancelled_single_run = True # cancel test

                message_box.exec()
                print("[INFO] User confirmed to run single script.")

            # --- End of new dialog block ---

        # Determine which runner to use 260104 For function test;
        if self.excel_plan_path is not None:
            # --- Mode 1: Run Excel Plan ---
            print(f"[DEBUG] Branch taken: Creating ExcelPlanRunner for '{self.excel_plan_path}'")
            try:
                self.runner = ExcelPlanRunner(self.excel_plan_path)
                print(f"[DEBUG] ExcelPlanRunner created successfully.")
            except Exception as e:
                self._append_log(f"<b style='color:red;'>Failed to create ExcelPlanRunner: {e}</b>")
                self._set_action_button("run")
                return
            # ----------------------------
        else:
            # --- Mode 2: Run Single Case (Original Logic) ---
            print(f"[DEBUG] Branch taken: Creating CaseRunner for '{self.case_path}'")
            self.runner = CaseRunner(
                self.case_path,
                account_name=account_name,
                display_case_path=self.display_case_path
            )
        #self.runner = CaseRunner(self.case_path, account_name=account_name, display_case_path=self.display_case_path)

        # Connect signals for both runners
        self.runner.log_signal.connect(self._append_log)
        self.runner.progress_signal.connect(self.update_progress)
        with suppress(Exception):
            self.runner.report_dir_signal.connect(self._on_report_dir_ready)
        # 连接完成信号：根据 runner 类型选择正确的信号
        if isinstance(self.runner, ExcelPlanRunner):
            self.runner.finished_signal.connect(self._finalize_runner)
        elif isinstance(self.runner, CaseRunner):
            self.runner.finished.connect(self._finalize_runner)  # ← 使用 QThread 内置信号
        else:
            raise TypeError(f"Unknown runner type: {type(self.runner)}")
        print(f"[DEBUG] Starting runner: {type(self.runner).__name__}")
        self.runner.start()

    # 260104 For function test;
    def set_excel_plan_path(self, path: str) -> None:
        """
        Set the path of the Excel test plan to be executed.
        This should be called before `run_case()`.
        """
        if not path or not Path(path).exists():
            raise ValueError(f"Invalid or non-existent Excel plan path: {path}")
        self.excel_plan_path = path
        # Update the UI header to show the plan name instead of the case path
        self.view.case_path_label.setText(f"Plan: {Path(path).name}")
        # Clear the single-case related state
        self.case_path = ""
        self.display_case_path = ""

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

            # --- 新增：按类型断开 finished 信号 ---
        if isinstance(runner, ExcelPlanRunner):
            with suppress((TypeError, RuntimeError)):
                runner.finished_signal.disconnect(self._finalize_runner)
        elif isinstance(runner, CaseRunner):
            with suppress((TypeError, RuntimeError)):
                runner.finished.disconnect(self._finalize_runner)

        runner.deleteLater()
        self.runner = None
        self.on_runner_finished()

    def _on_report_dir_ready(self, path: str) -> None:
        self._last_report_dir = path
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
        if self._last_report_dir:
            self.view.set_allure_report_dir(self._last_report_dir)

        # --- 260106 新增：通知主应用重置向导状态 ---
        print("[DEBUG] About to call reset_wizard_after_run")
        from src.ui.controller.run_ctl import reset_wizard_after_run
        reset_wizard_after_run(self)
        print("[DEBUG] reset_wizard_after_run called")

    def on_stop(self) -> None:
        self._append_log("on_stop entered")
        self.cleanup()
        self._stop_remaining_timer()
        self._set_action_button("run")
        self.action_btn.setEnabled(True)

    def _get_application_base(self) -> Path:
        # Get the directory of this file (run.py)
        current_file_dir = Path(__file__).resolve().parent
        # Go up: .../src/ui/view -> .../src/ui -> .../src -> project_root
        project_root = current_file_dir.parent.parent.parent
        print(f"[DEBUG] Calculated project root as: {project_root}")  # For verification
        return project_root

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
