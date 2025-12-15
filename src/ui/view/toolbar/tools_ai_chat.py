"""View for the AI chat tool.

This widget provides a simple chat-style interface similar to VS Code's
AI panels: model selection, message history, and an input box.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CardWidget, ComboBox

from src.ui.view.common import ChatMessageBubble
from src.ui.view.theme import FONT_FAMILY, FONT_SIZE, apply_tool_attach_button_style, apply_tool_input_box_style, apply_tool_send_button_style, apply_tool_text_style
from src.ui.view.builder import build_inline_fields_from_schema, load_ui_schema


class AiChatToolView(CardWidget):
    """UI for interactive AI chat."""

    sendMessageRequested = pyqtSignal(str)
    manageKeysRequested = pyqtSignal()
    attachFileRequested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aiChatToolView")
        self.setStyleSheet("background-color: #333333; border-radius: 8px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        # Header row similar to VS Code: title + model selector on the right
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title_label = QLabel("AI Chat", self)
        apply_tool_text_style(title_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)

        self.field_widgets = {}
        toolbar_schema = load_ui_schema("toolbar")
        for key, widget, label_text in build_inline_fields_from_schema(
            page=self,
            config={},
            ui_schema=toolbar_schema,
            panel_key="toolbar",
            section_id="ai_chat",
            parent=self,
        ):
            header_label = QLabel(f"{label_text}:", self)
            apply_tool_text_style(header_label)
            header_layout.addWidget(header_label)
            header_layout.addWidget(widget)
            self.field_widgets[key] = widget

        model_widget = self.field_widgets.get("toolbar.ai_chat.model_id")
        if isinstance(model_widget, ComboBox):
            self.model_combo = model_widget
        else:
            self.model_combo = ComboBox(self)
            fallback_label = QLabel("Model:", self)
            apply_tool_text_style(fallback_label)
            header_layout.addWidget(fallback_label)
            header_layout.addWidget(self.model_combo)

        manage_keys_button = QPushButton("API Keys", self)
        apply_tool_text_style(manage_keys_button)
        manage_keys_button.clicked.connect(self.manageKeysRequested.emit)
        header_layout.addWidget(manage_keys_button)
        layout.addLayout(header_layout)

        # Chat area: vertical list of message bubbles
        self.history_widget = QWidget(self)
        self.history_layout = QVBoxLayout(self.history_widget)
        self.history_layout.setContentsMargins(8, 8, 8, 8)
        self.history_layout.setSpacing(6)
        self.history_layout.addStretch(1)
        layout.addWidget(self.history_widget, 1)

        # Input block at the bottom, spanning full width
        input_block = QVBoxLayout()
        input_block.setContentsMargins(0, 0, 0, 0)
        input_block.setSpacing(6)

        self.input_edit = QPlainTextEdit(self)
        self.input_edit.setPlaceholderText("Ask the AI about your tests or configuration...")
        self.input_edit.setFont(QFont(FONT_FAMILY, FONT_SIZE))
        apply_tool_input_box_style(self.input_edit)
        input_block.addWidget(self.input_edit, 1)

        self.send_button = QPushButton(self.input_edit)
        apply_tool_send_button_style(self.send_button)
        self.attach_button = QPushButton(self.input_edit)
        apply_tool_attach_button_style(self.attach_button)

        def _on_send() -> None:
            text = self.input_edit.toPlainText().strip()
            if not text:
                return
            self.sendMessageRequested.emit(text)

        self.send_button.clicked.connect(_on_send)
        self.attach_button.clicked.connect(self.attachFileRequested.emit)

        layout.addLayout(input_block)
        self._update_send_button_position()

    def append_message(self, role: str, text: str) -> None:
        """Append a message bubble to the history view."""
        is_user = role == "user"
        bubble = ChatMessageBubble(text, is_user, parent=self.history_widget)
        index = max(0, self.history_layout.count() - 1)
        self.history_layout.insertWidget(index, bubble)

    def clear_input(self) -> None:
        self.input_edit.clear()

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self._update_send_button_position()

    def _update_send_button_position(self) -> None:
        rect = self.input_edit.rect()
        margin = 6
        spacing = 4
        send_x = rect.right() - self.send_button.width() - margin
        send_y = rect.bottom() - self.send_button.height() - margin
        self.send_button.move(send_x, send_y)

        attach_x = rect.left() + margin
        attach_y = send_y
        self.attach_button.move(attach_x, attach_y)
