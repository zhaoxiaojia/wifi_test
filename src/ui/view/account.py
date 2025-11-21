"""Account (login) page UI view and page.

This module contains both the *pure UI* widgets for the company
account sign‑in page and the ``CompanyLoginPage`` widget that wires
those widgets together.  Non‑UI logic for LDAP authentication lives in
``src.ui.controller.account_ctl``.
"""

from __future__ import annotations

import logging

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpacerItem,
    QSizePolicy,
    QLineEdit,
)
from qfluentwidgets import LineEdit, PushButton

from src.ui.view.theme import FONT_FAMILY, apply_theme
from .common import attach_view_to_page
from src.ui.controller.account_ctl import _LDAPAuthWorker


class AccountView(QWidget):
    """Pure UI for the account sign‑in page (no business logic)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("accountView")
        apply_theme(self, recursive=True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(120, 80, 120, 80)
        main_layout.setSpacing(24)
        main_layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Amlogic Account Sign In", self)
        title_font = QFont(FONT_FAMILY, 24)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        form_widget = QWidget(self)
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(16)
        form_layout.setContentsMargins(0, 0, 0, 0)

        self.account_edit = LineEdit(form_widget)
        self.account_edit.setPlaceholderText(
            "Account, e.g. your.name or your.name@amlogic.com"
        )
        form_layout.addWidget(self.account_edit)

        self.password_edit = LineEdit(form_widget)
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setEchoMode(QLineEdit.Password)
        form_layout.addWidget(self.password_edit)
        main_layout.addWidget(form_widget)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addItem(
            QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        self.login_button = PushButton("Sign In", self)
        button_row.addWidget(self.login_button)

        self.logout_button = PushButton("Sign Out", self)
        self.logout_button.setVisible(False)
        self.logout_button.setEnabled(False)
        button_row.addWidget(self.logout_button)

        button_row.addItem(
            QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )
        main_layout.addLayout(button_row)

        self.status_label = QLabel("", self)
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignCenter)
        status_font = QFont(FONT_FAMILY, 14)
        self.status_label.setFont(status_font)
        main_layout.addWidget(self.status_label)
        main_layout.addStretch(1)

        # Logical control map for the account page.
        # Keys follow: page_frame_group_purpose_type
        self.account_controls: dict[str, object] = {
            "account_main_title_label": title,
            "account_main_form_account_text": self.account_edit,
            "account_main_form_password_text": self.password_edit,
            "account_main_buttons_login_btn": self.login_button,
            "account_main_buttons_logout_btn": self.logout_button,
            "account_main_status_label": self.status_label,
        }


class CompanyLoginPage(QWidget):
    """
    Company account sign-in page that handles UI interactions and login state.

    Signals
    -------
    loginResult : pyqtSignal(bool, str, dict)
        Emitted when sign-in completes; provides success flag, message, and payload.
    logoutRequested : pyqtSignal()
        Emitted when the user clicks the Sign Out button.
    """

    loginResult = pyqtSignal(bool, str, dict)
    logoutRequested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the page layout, widgets, and signal wiring."""
        super().__init__(parent)
        self.setObjectName("companyLoginPage")
        self._loading = False
        self._logged_in = False
        self._auth_thread: QThread | None = None
        self._auth_worker: _LDAPAuthWorker | None = None
        self._last_payload: dict = {}
        apply_theme(self, recursive=True)

        # Compose the pure UI view and re‑export its widgets.
        self.view = AccountView(self)
        attach_view_to_page(self, self.view)

        # Convenience aliases so existing logic continues to work.
        self.account_edit: LineEdit = self.view.account_edit
        self.password_edit: LineEdit = self.view.password_edit
        self.login_button: PushButton = self.view.login_button
        self.logout_button: PushButton = self.view.logout_button
        self.status_label = self.view.status_label
        self.account_controls = self.view.account_controls

        # Wire button clicks to the existing slots on this page.
        self.login_button.clicked.connect(self._emit_login)
        self.logout_button.clicked.connect(self._emit_logout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_loading(self, loading: bool) -> None:
        """
        Enable or disable the loading state of the sign-in form.

        Parameters
        ----------
        loading : bool
            If True, disables input fields and shows waiting state.
        """
        self._loading = loading
        self.login_button.setEnabled(not loading and not self._logged_in)
        self.account_edit.setEnabled(not loading and not self._logged_in)
        self.password_edit.setEnabled(not loading and not self._logged_in)

    def set_status_message(self, message: str, *, state: str = "info") -> None:
        """
        Update the status message label with text and color.

        Parameters
        ----------
        message : str
            Text to display.
        state : str, optional
            One of {"info", "success", "error"} to determine color mapping.
        """
        color_map = {"info": "#2F80ED", "success": "#4CAF50", "error": "#FF6B6B"}
        color = color_map.get(state, color_map["info"])
        if message:
            self.status_label.setStyleSheet(f"color:{color};")
            self.status_label.setText(message)
        else:
            self.status_label.setStyleSheet("")
            self.status_label.clear()

    def set_login_result(self, success: bool, message: str = "", payload: dict | None = None) -> None:
        """
        Update login result state and broadcast via signal.

        Parameters
        ----------
        success : bool
            Whether the login succeeded.
        message : str, optional
            Feedback message to display.
        payload : dict | None, optional
            Additional info returned by the backend worker.
        """
        self._logged_in = success
        if payload is not None:
            self._last_payload = dict(payload)
        self.set_loading(False)

        if success:
            self.set_status_message(message or "Signed in successfully. Welcome!", state="success")
            self.login_button.setVisible(False)
            self.logout_button.setVisible(True)
            self.logout_button.setEnabled(True)
            self.account_edit.setEnabled(False)
            self.password_edit.setEnabled(False)
        else:
            self.set_status_message(message or "Sign-in failed. Please try again.", state="error")
            self.login_button.setVisible(True)
            self.login_button.setEnabled(True)
            self.logout_button.setVisible(False)
            self.logout_button.setEnabled(False)
            self.account_edit.setEnabled(True)
            self.password_edit.setEnabled(True)
            if not self._loading:
                self.password_edit.setFocus()
            self._last_payload = {}

        self.loginResult.emit(success, message, dict(self._last_payload))

    def reset(self) -> None:
        """Reset all input fields and restore default UI state."""
        self._loading = False
        self._logged_in = False
        self.account_edit.setEnabled(True)
        self.password_edit.setEnabled(True)
        self.account_edit.clear()
        self.password_edit.clear()
        self.login_button.setVisible(True)
        self.login_button.setEnabled(True)
        self.logout_button.setVisible(False)
        self.logout_button.setEnabled(False)
        self.status_label.setStyleSheet("")
        self.status_label.clear()

    # ------------------------------------------------------------------
    # Internal slots and helpers
    # ------------------------------------------------------------------

    def _emit_login(self) -> None:
        """Triggered when the Sign In button is pressed."""
        if self._logged_in or self._loading:
            return
        if self._auth_thread and self._auth_thread.isRunning():
            self.set_status_message("Login already in progress, please wait...")
            return

        account = self.account_edit.text().strip()
        password = self.password_edit.text()
        if not account or not password:
            self.set_status_message("Account or password cannot be empty.", state="error")
            return

        self.set_status_message("Sending LDAP authentication request... Please wait.")
        self.set_loading(True)
        self._start_auth_thread(account, password)

    def _emit_logout(self) -> None:
        """Triggered when the Sign Out button is pressed."""
        if self._auth_thread and self._auth_thread.isRunning():
            self.set_status_message("Logging out... waiting for current authentication to finish.")
            return
        self.reset()
        self.logoutRequested.emit()

    def _start_auth_thread(self, account: str, password: str) -> None:
        """
        Initialize and start a background thread for authentication.

        Parameters
        ----------
        account : str
            Username for LDAP.
        password : str
            Corresponding password.
        """
        self._auth_thread = QThread(self)
        self._auth_worker = _LDAPAuthWorker(account, password)
        self._auth_worker.moveToThread(self._auth_thread)
        self._auth_thread.started.connect(self._auth_worker.run)
        self._auth_worker.progress.connect(self.set_status_message)
        self._auth_worker.finished.connect(self._on_auth_finished)
        self._auth_worker.finished.connect(self._auth_thread.quit)
        self._auth_worker.finished.connect(self._auth_worker.deleteLater)
        self._auth_thread.finished.connect(self._auth_thread.deleteLater)
        self._auth_thread.finished.connect(self._clear_auth_thread)
        self._auth_thread.start()

    def _on_auth_finished(self, success: bool, message: str, payload: dict) -> None:
        """Handle worker completion and update UI accordingly."""
        logging.info(
            "CompanyLoginPage: authentication finished success=%s message=%s payload=%s",
            success,
            message,
            payload,
        )
        self.set_login_result(success, message, payload)

    def _clear_auth_thread(self) -> None:
        """Clean up thread and worker references after thread termination."""
        self._auth_thread = None
        self._auth_worker = None


__all__ = ["AccountView", "CompanyLoginPage"]

