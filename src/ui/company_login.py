#!/usr/bin/env python
# encoding: utf-8
"""Amlogic company account sign-in page (LDAP)."""
from __future__ import annotations

import logging
import os

from ldap3 import ALL, Connection, NTLM, Server
from ldap3.core.exceptions import LDAPException
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


LDAP_HOST = os.getenv("AMLOGIC_LDAP_HOST", "ldap.amlogic.com")
LDAP_DOMAIN = os.getenv("AMLOGIC_LDAP_DOMAIN", "AMLOGIC")


def get_configured_ldap_server() -> str:
    """返回当前配置的 LDAP 服务器主机名。"""

    return LDAP_HOST


def ldap_authenticate(username: str, password: str) -> str | None:
    """使用公司 LDAP 服务验证登录凭证。"""

    clean_username = (username or "").strip()
    if not clean_username or not password:
        logging.info("ldap_authenticate: 账号或密码为空 (username=%s)", clean_username)
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
            logging.warning(
                "ldap_authenticate: LDAP bind failed (username=%s, server=%s, result=%s)",
                domain_user,
                server_host,
                connection.result,
            )
            return None
        logging.info(
            "ldap_authenticate: LDAP bind success (username=%s, server=%s)",
            domain_user,
            server_host,
        )
        return clean_username
    except LDAPException as exc:
        logging.error(
            "ldap_authenticate: LDAP 异常 (username=%s, server=%s): %s",
            clean_username,
            server_host,
            exc,
        )
        return None

    finally:
        if connection is not None:
            try:
                connection.unbind()
            except Exception:  # pragma: no cover - 清理阶段无需抛出
                logging.debug("ldap_authenticate: 忽略 unbind 异常", exc_info=True)


def _normalize_username(username: str) -> str:
    """根据是否包含域信息拼接完整账号。"""

    clean_username = username.strip()
    if "\\" in clean_username or "@" in clean_username:
        return clean_username
    return f"{LDAP_DOMAIN}\\{clean_username}"


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
