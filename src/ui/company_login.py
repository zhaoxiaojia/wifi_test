#!/usr/bin/env python
# encoding: utf-8
"""Amlogic company account sign-in page (LDAP)."""
from __future__ import annotations

import logging
import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpacerItem,
    QSizePolicy,
)
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QLineEdit
from ldap3 import ALL, Connection, NTLM, Server
from ldap3.core.exceptions import LDAPException
from qfluentwidgets import LineEdit, PushButton

from .theme import FONT_FAMILY
from .theme import apply_theme

LDAP_SERVER = os.getenv("AMLOGIC_LDAP_SERVER", "ldaps://ad.amlogic.com")
LDAP_DOMAIN = os.getenv("AMLOGIC_LDAP_DOMAIN", "amlogic.com")


def _normalize_account(account: str) -> str:
    """Return an account with domain prefix when necessary."""

    clean_account = account.strip()
    if "\\" in clean_account or "@" in clean_account:
        return clean_account
    return f"{LDAP_DOMAIN}\\{clean_account}"


def create_ldap_server(host: str | None = None) -> Server:
    """Create an LDAP :class:`Server` following the official example."""

    server_host = (host or LDAP_SERVER).strip()
    return Server(server_host, get_info=ALL)


def create_ldap_connection(server: Server, account: str, password: str) -> Connection:
    """Create an LDAP :class:`Connection` configured for NTLM authentication."""

    normalized_account = _normalize_account(account)
    return Connection(
        server,
        user=normalized_account,
        password=password,
        authentication=NTLM,
    )


def authenticate_via_ldap(account: str, password: str) -> tuple[bool, str]:
    """Authenticate a company account via LDAP and return (success, message)."""

    clean_account = (account or "").strip()
    if not clean_account or not password:
        logging.info(
            "authenticate_via_ldap: 账号或密码为空 (account=%s)",
            clean_account,
        )
        return False, "Account or password cannot be empty."

    server = create_ldap_server()
    connection: Connection | None = None
    try:
        connection = create_ldap_connection(server, clean_account, password)
        if not connection.bind():
            logging.info(
                "authenticate_via_ldap: LDAP bind failed -> %s",
                connection.result,
            )
            return False, "LDAP bind failed. Please verify your credentials."
        logging.info("authenticate_via_ldap: LDAP bind success")
        return True, clean_account
    except LDAPException as exc:
        logging.error("authenticate_via_ldap: LDAP 异常 -> %s", exc)
        return False, "LDAP authentication error."
    finally:
        if connection is not None:
            try:
                connection.unbind()
            except Exception:  # pragma: no cover - cleanup should not raise
                logging.debug(
                    "authenticate_via_ldap: 忽略 unbind 异常",
                    exc_info=True,
                )


class CompanyLoginPage(QWidget):
    """Company account sign-in page that collects credentials and emits related signals."""

    loginRequested = pyqtSignal(str, str)
    """Emitted when the user clicks the sign-in button with (account, password)."""

    loginResult = pyqtSignal(bool, str)
    """Emitted after sign-in completes with (success, message)."""

    logoutRequested = pyqtSignal()
    """Emitted when the user clicks the sign-out button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("companyLoginPage")
        self._loading = False
        self._logged_in = False
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

    # ------------------------------ public api ------------------------------
    def set_loading(self, loading: bool) -> None:
        """Toggle loading state of the sign-in button and inputs."""
        self._loading = loading
        self.login_button.setEnabled(not loading and not self._logged_in)
        self.account_edit.setEnabled(not loading and not self._logged_in)
        self.password_edit.setEnabled(not loading and not self._logged_in)

    def set_status_message(self, message: str, *, state: str = "info") -> None:
        """Update status label text and color."""
        color_map = {
            "info": "#2F80ED",
            "success": "#4CAF50",
            "error": "#FF6B6B",
        }
        color = color_map.get(state, color_map["info"])
        if message:
            self.status_label.setStyleSheet(f"color:{color};")
            self.status_label.setText(message)
        else:
            self.status_label.setStyleSheet("")
            self.status_label.clear()

    def set_login_result(self, success: bool, message: str = "") -> None:
        """Update login state and emit the result."""
        self._logged_in = success
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
        self.loginResult.emit(success, message)

    def reset(self) -> None:
        """Reset inputs and UI state."""
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

    # ------------------------------ slots ------------------------------
    def _emit_login(self) -> None:
        if self._logged_in or self._loading:
            return
        account = self.account_edit.text().strip()
        password = self.password_edit.text()
        self.set_status_message("Submitting LDAP sign-in request...")
        self.set_loading(True)
        self.loginRequested.emit(account, password)

    def _emit_logout(self) -> None:
        self.reset()
        self.logoutRequested.emit()
