"""View for the AI chat tool.

This widget provides a simple chat-style interface similar to VS Code's
AI panels: model selection, message history, and an input box.
"""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CardWidget, ComboBox

from src.ui.view.theme import apply_tool_input_box_style, apply_tool_send_button_style, apply_tool_text_style


class AiChatToolView(CardWidget):
    """UI for interactive AI chat."""

    sendMessageRequested = pyqtSignal(str)
    modelChanged = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aiChatToolView")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header row similar to VS Code: title + model selector on the right
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title_label = QLabel("AI Chat", self)
        apply_tool_text_style(title_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        header_model_label = QLabel("Model:", self)
        apply_tool_text_style(header_model_label)
        self.model_combo = ComboBox(self)
        self.model_combo.addItems(["free-llm-1", "free-llm-2"])
        self.model_combo.currentTextChanged.connect(
            lambda name: self.modelChanged.emit(str(name))
        )
        header_layout.addWidget(header_model_label)
        header_layout.addWidget(self.model_combo)
        layout.addLayout(header_layout)

        # Chat area
        self.history_view = QTextEdit(self)
        self.history_view.setReadOnly(True)
        apply_tool_input_box_style(self.history_view)
        layout.addWidget(self.history_view, 1)

        # Input block at the bottom, spanning full width
        input_block = QVBoxLayout()
        input_block.setContentsMargins(0, 0, 0, 0)
        input_block.setSpacing(6)

        self.input_edit = QPlainTextEdit(self)
        self.input_edit.setPlaceholderText("Ask the AI about your tests or configuration...")
        apply_tool_input_box_style(self.input_edit)
        input_block.addWidget(self.input_edit, 1)

        self.send_button = QPushButton(self.input_edit)
        apply_tool_send_button_style(self.send_button)

        def _on_send() -> None:
            text = self.input_edit.toPlainText().strip()
            if not text:
                return
            self.sendMessageRequested.emit(text)

        self.send_button.clicked.connect(_on_send)

        layout.addLayout(input_block)
        self._update_send_button_position()

    def append_message(self, role: str, text: str) -> None:
        """Append a message to the history view."""
        prefix = "You: " if role == "user" else "AI: "
        self.history_view.append(f"{prefix}{text}")

    def clear_input(self) -> None:
        self.input_edit.clear()

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self._update_send_button_position()

    def _update_send_button_position(self) -> None:
        rect = self.input_edit.rect()
        margin = 6
        x = rect.right() - self.send_button.width() - margin
        y = rect.bottom() - self.send_button.height() - margin
        self.send_button.move(x, y)
