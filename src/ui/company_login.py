#!/usr/bin/env python
# encoding: utf-8
"""
Amlogic Company LDAP Sign-In Page.

This module implements both the UI and backend authentication logic for
Amlogic’s corporate LDAP-based login system. It provides:

- A Qt-based login page for collecting credentials and showing status.
- A background worker that performs authentication using the ldap3 library.
- Helper utilities for username normalization and connection cleanup.

The design separates UI and network logic via QThread to keep the main GUI
responsive. It’s intended to be embedded in desktop tools that require
corporate authentication before accessing restricted features.
"""

from __future__ import annotations

import logging
import os

from ldap3 import ALL, Connection, NTLM, Server
from ldap3.core.exceptions import LDAPException
from PyQt5.QtCore import QObject, Qt, pyqtSignal, QThread
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpacerItem,
    QSizePolicy,
    QLineEdit,
)
from PyQt5.QtGui import QFont
from qfluentwidgets import LineEdit, PushButton

from .theme import FONT_FAMILY, apply_theme

# -----------------------------------------------------------------------------
# Global constants
# -----------------------------------------------------------------------------

LDAP_HOST = os.getenv("AMLOGIC_LDAP_HOST", "ldap.amlogic.com")
"""Default LDAP host used by the company authentication system."""

LDAP_DOMAIN = os.getenv("AMLOGIC_LDAP_DOMAIN", "AMLOGIC")
"""Default NTLM domain used for username normalization."""


# -----------------------------------------------------------------------------
# Background worker
# -----------------------------------------------------------------------------

class _LDAPAuthWorker(QObject):
    """
    Background worker that performs LDAP authentication in a separate thread.

    Signals
    -------
    finished : pyqtSignal(bool, str, dict)
        Emitted when authentication completes; carries (success, message, payload).
    progress : pyqtSignal(str)
        Emitted with progress or status messages to display in the UI.

    Parameters
    ----------
    username : str
        Username provided by the user (can be bare name or domain-qualified).
    password : str
        Plaintext password.
    """

    finished = pyqtSignal(bool, str, dict)
    progress = pyqtSignal(str)

    def __init__(self, username: str, password: str) -> None:
        super().__init__()
        self._username = (username or "").strip()
        self._password = password or ""

    def run(self) -> None:  # pragma: no cover
        """
        Perform LDAP authentication on the background thread.

        Emits
        -----
        finished(bool, str, dict)
            Always emitted with the final result, even on error.
        """
        if not self._username or not self._password:
            message = "Account or password cannot be empty."
            logging.warning("LDAP login failed: missing username or password")
            self.finished.emit(False, message, {})
            return

        server_host = LDAP_HOST.strip()
        self.progress.emit(f"Connecting to LDAP server: {server_host}")
        success, message, payload = _ldap_authenticate(self._username, self._password)
        self.finished.emit(success, message, payload)


# -----------------------------------------------------------------------------
# LDAP helpers
# -----------------------------------------------------------------------------

def _ldap_authenticate(username: str, password: str) -> tuple[bool, str, dict]:
    """
    Perform LDAP authentication using the `ldap3` library.

    Parameters
    ----------
    username : str
        The username provided by the user.
    password : str
        The associated password.

    Returns
    -------
    tuple[bool, str, dict]
        - success (bool): True if authentication succeeded.
        - message (str): Human-readable status.
        - payload (dict): Additional info (e.g., username, server).
    """
    clean_username = username.strip()
    domain_user = _normalize_username(clean_username)
    server_host = LDAP_HOST.strip()
    connection: Connection | None = None

    try:
        server = Server(server_host, get_info=ALL)
        connection = Connection(
            server,
            user=domain_user,
            password=password,
            authentication=NTLM,
        )
        if connection.bind():
            logging.info("LDAP authentication succeeded (username=%s, server=%s)", domain_user, server_host)
            payload = {"username": clean_username, "server": server_host}
            return True, f"Sign-in successful. Welcome, {clean_username}", payload

        logging.warning("LDAP bind failed (username=%s, server=%s, result=%s)", domain_user, server_host, connection.result)
        return False, "LDAP sign-in failed. Please check your account or password.", {}

    except LDAPException as exc:
        logging.error("LDAP connection/authentication exception (username=%s, server=%s): %s", clean_username, server_host, exc)
        return False, f"Sign-in failed: {exc}", {}

    finally:
        if connection is not None:
            try:
                connection.unbind()
            except Exception:
                logging.debug("LDAP unbind raised an exception and was ignored.", exc_info=True)


def _normalize_username(username: str) -> str:
    """
    Normalize username by ensuring the proper domain prefix.

    If the username already contains ``\\`` or ``@``, it is returned as-is.
    Otherwise, the company’s default domain prefix is added.

    Parameters
    ----------
    username : str
        Raw username string.

    Returns
    -------
    str
        Fully qualified username with domain.
    """
    clean_username = username.strip()
    if "\\" in clean_username or "@" in clean_username:
        return clean_username
    return f"{LDAP_DOMAIN}\\{clean_username}"


def get_configured_ldap_server() -> str:
    """
    Return the currently configured LDAP host name.

    Returns
    -------
    str
        Host name of the LDAP server.
    """
    return LDAP_HOST


def ldap_authenticate(username: str, password: str) -> str | None:
    """
    Lightweight synchronous LDAP authentication helper.

    Performs a bind test against the configured server. Intended for quick
    credential checks that do not require thread-based async logic.

    Parameters
    ----------
    username : str
        User name to authenticate.
    password : str
        Corresponding password.

    Returns
    -------
    str | None
        The validated username if successful, otherwise None.
    """
    clean_username = (username or "").strip()
    if not clean_username or not password:
        logging.info("ldap_authenticate: username or password empty (username=%s)", clean_username)
        return None

    server_host = LDAP_HOST.strip()
    connection: Connection | None = None
    try:
        server = Server(server_host, get_info=ALL)
        domain_user = _normalize_username(clean_username)
        connection = Connection(
            server,
            user=domain_user,
            password=password,
            authentication=NTLM,
        )
        if not connection.bind():
            logging.warning("ldap_authenticate: LDAP bind failed (username=%s, server=%s, result=%s)", domain_user, server_host, connection.result)
            return None
        logging.info("ldap_authenticate: LDAP bind success (username=%s, server=%s)", domain_user, server_host)
        return clean_username
    except LDAPException as exc:
        logging.error("ldap_authenticate: LDAP exception (username=%s, server=%s): %s", clean_username, server_host, exc)
        return None
    finally:
        if connection is not None:
            try:
                connection.unbind()
            except Exception:
                logging.debug("ldap_authenticate: ignored unbind exception", exc_info=True)


# -----------------------------------------------------------------------------
# Main Login Page
# -----------------------------------------------------------------------------

class CompanyLoginPage(QWidget):
    """
    Company account sign-in page that handles UI interactions and login state.

    Signals
    -------
    loginResult : pyqtSignal(bool, str, dict)
        Emitted when sign-in completes; provides success flag, message, and payload.
    logoutRequested : pyqtSignal()
        Emitted when the user clicks the Sign Out button.

    Notes
    -----
    This widget uses :class:`_LDAPAuthWorker` for the background authentication
    process, ensuring that the main thread remains responsive while network
    operations run on a worker thread.
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
        self.account_edit.setPlaceholderText("Account, e.g. your.name or your.name@amlogic.com")
        form_layout.addWidget(self.account_edit)

        self.password_edit = LineEdit(form_widget)
        self.password_edit.setPlaceholderText("Password")
        self.password_edit.setEchoMode(QLineEdit.Password)
        form_layout.addWidget(self.password_edit)
        main_layout.addWidget(form_widget)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.login_button = PushButton("Sign In", self)
        self.login_button.clicked.connect(self._emit_login)
        button_row.addWidget(self.login_button)

        self.logout_button = PushButton("Sign Out", self)
        self.logout_button.clicked.connect(self._emit_logout)
        self.logout_button.setVisible(False)
        self.logout_button.setEnabled(False)
        button_row.addWidget(self.logout_button)

        button_row.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
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

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

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

    # ---------------------------------------------------------------------
    # Internal slots and helpers
    # ---------------------------------------------------------------------

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
        logging.info("CompanyLoginPage: authentication finished success=%s message=%s payload=%s", success, message, payload)
        self.set_login_result(success, message, payload)

    def _clear_auth_thread(self) -> None:
        """Clean up thread and worker references after thread termination."""
        self._auth_thread = None
        self._auth_worker = None
