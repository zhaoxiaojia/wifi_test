"""Controller for the AI chat tool.

This controller connects :class:`AiChatToolView` to an AI backend.  The
current implementation is a stub that can be extended to call a free
LLM based on the selected model.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from src.ui.view.tools_ai_chat import AiChatToolView
from src.ui.model.ai_chat_backend import (
    get_signup_url,
    list_models_for_ui,
    load_api_key,
    send_chat_completion,
    store_api_key,
)


class AiChatToolController:
    """Behaviour for the AI chat tool."""

    def __init__(self, view: AiChatToolView, parent: Optional[QWidget] = None) -> None:
        self.view = view
        self.parent = parent or view
        self._current_model_id: str | None = None

        models = list_models_for_ui()
        if models:
            self.view.model_combo.clear()
            for model_id, title in models:
                self.view.model_combo.addItem(title, userData=model_id)

        self.view.model_combo.currentIndexChanged.connect(self._on_model_index_changed)
        self._on_model_index_changed(self.view.model_combo.currentIndex())

        self.view.sendMessageRequested.connect(self._on_send_message)
        self.view.manageKeysRequested.connect(self._on_manage_keys_requested)
        self.view.attachFileRequested.connect(self._on_attach_file_requested)

    def _on_model_index_changed(self, index: int) -> None:
        model_id = self.view.model_combo.itemData(index)
        if isinstance(model_id, str):
            self._current_model_id = model_id

    def _on_send_message(self, text: str) -> None:
        """Handle a user message from the view."""
        self.view.append_message("user", text)
        self.view.clear_input()
        try:
            model_id = self._current_model_id
            if not model_id:
                reply = "No model is selected."
            else:
                try:
                    reply = send_chat_completion(model_id, text)
                except RuntimeError as exc:
                    signup_url = get_signup_url(model_id)
                    self._prompt_for_signup(signup_url, str(exc))
                    reply = str(exc)
        except Exception as exc:  # noqa: BLE001
            reply = f"Error calling model: {exc}"
        self.view.append_message("assistant", reply)

    def _prompt_for_signup(self, url: str, message: str) -> None:
        box = QMessageBox(self.parent)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("API key required")
        box.setText(message)
        box.setInformativeText(
            "Open the provider web site in your browser to create or view an API key?"
        )
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        result = box.exec_()
        if result == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(url))

    def _on_manage_keys_requested(self) -> None:
        model_id = self._current_model_id
        if not model_id:
            box = QMessageBox(self.parent)
            box.setIcon(QMessageBox.Information)
            box.setWindowTitle("No model selected")
            box.setText("Select a model before editing API keys.")
            box.setStandardButtons(QMessageBox.Ok)
            box.exec_()
            return

        current_title = self.view.model_combo.currentText() or model_id
        existing_key = load_api_key(model_id)

        dialog = _ApiKeyDialog(self.parent, current_title, existing_key)
        if dialog.exec_() == QDialog.Accepted:
            api_key = dialog.api_key()
            if api_key:
                store_api_key(model_id, api_key)

    def _on_attach_file_requested(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.parent, "Select file to attach", "", "All Files (*.*)"
        )
        if path:
            self.view.append_message("user", f"[Attached file] {path}")


class _ApiKeyDialog(QDialog):
    """Simple dialog to edit a single provider API key."""

    def __init__(self, parent: QWidget, model_title: str, api_key: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{model_title} API Key")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._key_edit = QLineEdit(self)
        self._key_edit.setText(api_key)
        self._key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("API Key:", self._key_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def api_key(self) -> str:
        return self._key_edit.text().strip()

__all__ = ["AiChatToolController"]
