"""Run page UI view.

This module defines a pure-UI view for the Run page. Behaviour such as
log streaming, remaining-time calculation and pytest integration remain
implemented in :mod:`run_page`, which composes this view and wires
signals/slots.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout
from qfluentwidgets import CardWidget, PushButton, StrongBodyLabel

from src.ui.view.theme import (
    ACCENT_COLOR,
    CONTROL_HEIGHT,
    FONT_FAMILY,
    apply_theme,
)


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

