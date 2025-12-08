"""View for the BT FW log analysis tool.

This widget only defines the layout for serial configuration, file
selection, and result display.  Behaviour and I/O are implemented in
the corresponding controller.
"""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CardWidget, LineEdit, PushButton

from src.ui.view.theme import apply_theme, apply_tool_input_box_style, apply_tool_text_style


class BtFwLogToolView(CardWidget):
    """UI for configuring and running BT FW log analysis."""

    browseFileRequested = pyqtSignal()
    analyzeRequested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("btFwLogToolView")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Serial configuration
        serial_group = QGroupBox("Serial configuration", self)
        serial_layout = QFormLayout(serial_group)
        serial_layout.setContentsMargins(8, 8, 8, 8)
        self.port_edit = LineEdit(serial_group)
        self.port_edit.setPlaceholderText("COM port (e.g. COM3)")
        apply_tool_input_box_style(self.port_edit)
        self.baud_edit = LineEdit(serial_group)
        self.baud_edit.setPlaceholderText("Baud rate (e.g. 115200)")
        apply_tool_input_box_style(self.baud_edit)
        serial_layout.addRow("Port:", self.port_edit)
        serial_layout.addRow("Baud:", self.baud_edit)
        layout.addWidget(serial_group)

        # Log file selection
        file_group = QGroupBox("Log file", self)
        file_layout = QHBoxLayout(file_group)
        file_layout.setContentsMargins(8, 8, 8, 8)
        self.file_path_edit = LineEdit(file_group)
        self.file_path_edit.setReadOnly(True)
        apply_tool_input_box_style(self.file_path_edit)
        browse_button = PushButton("Browse", file_group)
        apply_tool_text_style(browse_button)
        browse_button.clicked.connect(lambda: self.browseFileRequested.emit())
        file_layout.addWidget(self.file_path_edit, 1)
        file_layout.addWidget(browse_button)
        layout.addWidget(file_group)

        # Action buttons
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)
        self.analyze_button = PushButton("Analyze", self)
        apply_tool_text_style(self.analyze_button)
        self.analyze_button.clicked.connect(lambda: self.analyzeRequested.emit())
        action_layout.addStretch(1)
        action_layout.addWidget(self.analyze_button)
        layout.addLayout(action_layout)

        # Result view
        self.result_view = QTextEdit(self)
        self.result_view.setReadOnly(True)
        layout.addWidget(self.result_view, 1)

        apply_theme(self, recursive=False)

    def set_file_path(self, path: str) -> None:
        self.file_path_edit.setText(path)

    def append_result_text(self, text: str) -> None:
        self.result_view.append(text)
