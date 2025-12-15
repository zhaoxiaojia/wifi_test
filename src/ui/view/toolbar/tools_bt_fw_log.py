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
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CardWidget, ComboBox, LineEdit, PushButton

from src.ui.view.theme import (
    apply_theme,
    apply_tool_input_box_style,
    apply_tool_progress_style,
    apply_tool_text_style,
)


class BtFwLogToolView(CardWidget):
    """UI for configuring and running BT FW log analysis."""

    browseFileRequested = pyqtSignal()
    analyzeRequested = pyqtSignal()
    captureRequested = pyqtSignal(bool)

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
        # Use the default qfluentwidgets ComboBox styling here so that
        # the appearance matches the Config page's Serial Port controls.
        # Applying the text-input style to combo boxes introduces an
        # inner scroll area, which is why the BT toolbar version showed
        # an unexpected scrollbar.
        self.port_combo = ComboBox(serial_group)
        self.baud_combo = ComboBox(serial_group)
        serial_layout.addRow("Port:", self.port_combo)
        serial_layout.addRow("Baud:", self.baud_combo)

        # Serial capture + analysis entry: start/stop from inside the
        # Serial configuration group. Align the button to the right so
        # that it visually matches the Browse button alignment below.
        self.capture_button = PushButton("Start analyze", serial_group)
        self.capture_button.setCheckable(True)
        apply_tool_text_style(self.capture_button)
        self.capture_button.clicked.connect(self._on_capture_clicked)
        capture_row = QWidget(serial_group)
        capture_layout = QHBoxLayout(capture_row)
        capture_layout.setContentsMargins(0, 0, 0, 0)
        capture_layout.addStretch(1)
        capture_layout.addWidget(self.capture_button)
        serial_layout.addRow("", capture_row)

        layout.addWidget(serial_group)

        # Log file selection
        file_group = QGroupBox("Log file", self)
        file_layout = QHBoxLayout(file_group)
        file_layout.setContentsMargins(8, 8, 8, 8)

        # Composite widget so that the Browse button appears visually
        # inside the text box on the right-hand side.
        file_box = QWidget(file_group)
        box_layout = QHBoxLayout(file_box)
        box_layout.setContentsMargins(8, 2, 8, 2)
        box_layout.setSpacing(4)
        apply_tool_input_box_style(file_box)

        self.file_path_edit = LineEdit(file_box)
        self.file_path_edit.setReadOnly(True)
        # Let the outer box provide the border; keep the line edit flat.
        self.file_path_edit.setStyleSheet("border: none; background: transparent;")

        browse_button = PushButton("Browse", file_box)
        apply_tool_text_style(browse_button)
        browse_button.clicked.connect(lambda: self.browseFileRequested.emit())

        box_layout.addWidget(self.file_path_edit, 1)
        box_layout.addWidget(browse_button)

        file_layout.addWidget(file_box)
        layout.addWidget(file_group)

        # Hidden analyze button used only for programmatic triggering
        # when a local file is selected. It is not visible in the UI.
        self.analyze_button = PushButton("Analyze", self)
        self.analyze_button.clicked.connect(lambda: self.analyzeRequested.emit())
        self.analyze_button.hide()

        # Lightweight busy indicator shown during long‑running analysis.
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)  # Indeterminate / busy state.
        apply_tool_progress_style(self.progress_bar)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Result view
        self.result_view = QTextEdit(self)
        self.result_view.setReadOnly(True)
        layout.addWidget(self.result_view, 1)

        apply_theme(self, recursive=False)

    def set_file_path(self, path: str) -> None:
        self.file_path_edit.setText(path)

    def append_result_text(self, text: str) -> None:
        self.result_view.append(text)

    # ------------------------------------------------------------------
    # Serial config helpers
    # ------------------------------------------------------------------

    def set_serial_ports(self, labels: list[str]) -> None:
        """Populate the port combo with the given labels."""
        self.port_combo.clear()
        if not labels:
            # Keep the combo enabled so the user understands this
            # state is "no ports found" rather than a broken widget.
            self.port_combo.addItem("No serial ports detected")
            return
        for label in labels:
            self.port_combo.addItem(label)

    def set_baud_rates(self, rates: list[str]) -> None:
        """Populate the baud combo with standard baud rates."""
        self.baud_combo.clear()
        if not rates:
            return
        for rate in rates:
            self.baud_combo.addItem(rate)
        # Keep the first entry selected by default.
        if self.baud_combo.count() > 0:
            self.baud_combo.setCurrentIndex(0)

    def current_port_label(self) -> str:
        text = self.port_combo.currentText().strip()
        if text == "No serial ports detected":
            return ""
        return text

    def current_baud_rate(self) -> int:
        text = self.baud_combo.currentText().strip()
        try:
            return int(text)
        except (TypeError, ValueError):
            return 115200

    def set_capture_running(self, running: bool) -> None:
        self.capture_button.setChecked(running)
        self.capture_button.setText("Stop analyze" if running else "Start analyze")

    def set_busy(self, busy: bool) -> None:
        """Show or hide the indeterminate progress bar."""
        self.progress_bar.setVisible(busy)

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_capture_clicked(self) -> None:
        running = self.capture_button.isChecked()
        self.set_capture_running(running)
        self.captureRequested.emit(running)
