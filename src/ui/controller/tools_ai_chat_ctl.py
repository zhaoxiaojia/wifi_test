"""Controller for the AI chat tool.

This controller connects :class:`AiChatToolView` to an AI backend.  The
current implementation is a stub that can be extended to call a free
LLM based on the selected model.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import QWidget

from src.ui.view.tools_ai_chat import AiChatToolView


class AiChatToolController:
    """Behaviour for the AI chat tool."""

    def __init__(self, view: AiChatToolView, parent: Optional[QWidget] = None) -> None:
        self.view = view
        self.parent = parent or view
        self._current_model = self.view.model_combo.currentText()

        self.view.modelChanged.connect(self._on_model_changed)
        self.view.sendMessageRequested.connect(self._on_send_message)

    def _on_model_changed(self, name: str) -> None:
        self._current_model = name

    def _on_send_message(self, text: str) -> None:
        """Handle a user message from the view."""
        self.view.append_message("user", text)
        self.view.clear_input()
        self.view.append_message("assistant", "AI reply is not implemented yet.")


__all__ = ["AiChatToolController"]
