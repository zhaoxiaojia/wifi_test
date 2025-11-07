#!/usr/bin/env python
# encoding: utf-8
"""Amlogic 公司账号登录页面。"""
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
)
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QLineEdit
from qfluentwidgets import LineEdit, PushButton

from .theme import FONT_FAMILY
from .theme import apply_theme

LDAP_HOST = os.getenv("AMLOGIC_LDAP_HOST", "ldap.amlogic.com")
LDAP_DOMAIN = os.getenv("AMLOGIC_LDAP_DOMAIN", "AMLOGIC")


class _LDAPAuthWorker(QObject):
    """在后台线程执行 LDAP 认证逻辑。"""

    finished = pyqtSignal(bool, str, dict)
    progress = pyqtSignal(str)

    def __init__(self, username: str, password: str) -> None:
        super().__init__()
        self._username = (username or "").strip()
        self._password = password or ""

    def run(self) -> None:  # pragma: no cover - 后台线程执行
        if not self._username or not self._password:
            message = "账号或密码不能为空。"
            logging.warning("LDAP 登录失败：缺少账号或密码")
            self.finished.emit(False, message, {})
            return

        server_host = LDAP_HOST.strip()
        self.progress.emit(f"正在连接 LDAP 服务器：{server_host}")
        success, message, payload = _ldap_authenticate(self._username, self._password)
        self.finished.emit(success, message, payload)


def _ldap_authenticate(username: str, password: str) -> tuple[bool, str, dict]:
    """复用示例代码执行 LDAP 验证。"""

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
            logging.info(
                "LDAP 认证成功 (username=%s, server=%s)",
                domain_user,
                server_host,
            )
            payload = {
                "username": clean_username,
                "server": server_host,
            }
            return True, f"登录成功，欢迎 {clean_username}", payload
        logging.warning(
            "LDAP 认证失败 (username=%s, server=%s, result=%s)",
            domain_user,
            server_host,
            connection.result,
        )
        return False, "LDAP 登录失败，请检查账号或密码。", {}
    except LDAPException as exc:
        logging.error(
            "LDAP 连接或认证异常 (username=%s, server=%s): %s",
            clean_username,
            server_host,
            exc,
        )
        return False, f"登录失败：{exc}", {}
    finally:
        if connection is not None:
            try:
                connection.unbind()
            except Exception:  # pragma: no cover - 释放阶段忽略异常
                logging.debug("LDAP unbind 时发生异常，已忽略", exc_info=True)


def _normalize_username(username: str) -> str:
    """根据是否包含域信息拼接完整账号。"""

    clean_username = username.strip()
    if "\\" in clean_username or "@" in clean_username:
        return clean_username
    return f"{LDAP_DOMAIN}\\{clean_username}"


class CompanyLoginPage(QWidget):
    """公司账号登录页，收集凭据并对外暴露登录相关信号。"""

    loginResult = pyqtSignal(bool, str, dict)
    """登录完成后发出 (success, message, payload)"""

    logoutRequested = pyqtSignal()
    """用户点击注销按钮时发出"""

    def __init__(self, parent: QWidget | None = None) -> None:
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

        title = QLabel("Amlogic 公司账户登录", self)
        title_font = QFont(FONT_FAMILY, 24)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        form_widget = QWidget(self)
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(16)
        form_layout.setContentsMargins(0, 0, 0, 0)

        self.account_edit = LineEdit(form_widget)
        self.account_edit.setPlaceholderText("账号，例如 your.name 或 your.name@amlogic.com")
        form_layout.addWidget(self.account_edit)

        self.password_edit = LineEdit(form_widget)
        self.password_edit.setPlaceholderText("密码")
        self.password_edit.setEchoMode(QLineEdit.Password)
        form_layout.addWidget(self.password_edit)

        main_layout.addWidget(form_widget)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        button_row.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.login_button = PushButton("登录", self)
        # self.login_button.setIcon(FluentIcon.LOGIN)
        self.login_button.clicked.connect(self._emit_login)
        button_row.addWidget(self.login_button)

        self.logout_button = PushButton("注销", self)
        # self.logout_button.setIcon(FluentIcon.SIGN_OUT)
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
        """切换登录按钮加载状态"""
        self._loading = loading
        self.login_button.setEnabled(not loading and not self._logged_in)
        self.account_edit.setEnabled(not loading and not self._logged_in)
        self.password_edit.setEnabled(not loading and not self._logged_in)

    def set_status_message(self, message: str, *, state: str = "info") -> None:
        """更新状态标签文案及颜色。"""

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

    def set_login_result(
        self,
        success: bool,
        message: str = "",
        payload: dict | None = None,
    ) -> None:
        """更新登录状态并对外广播结果"""
        self._logged_in = success
        if payload is not None:
            self._last_payload = dict(payload)
        self.set_loading(False)
        if success:
            self.set_status_message(message or "登录成功，欢迎使用！", state="success")
            self.login_button.setVisible(False)
            self.logout_button.setVisible(True)
            self.logout_button.setEnabled(True)
            self.account_edit.setEnabled(False)
            self.password_edit.setEnabled(False)
        else:
            self.set_status_message(message or "登录失败，请重试。", state="error")
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
        """重置输入框与状态"""
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
        if self._auth_thread and self._auth_thread.isRunning():
            self.set_status_message("登录正在进行，请稍候…")
            return
        account = self.account_edit.text().strip()
        password = self.password_edit.text()
        if not account or not password:
            self.set_status_message("账号或密码不能为空。", state="error")
            return
        self.set_status_message("正在发起 LDAP 登录请求，请稍候…")
        self.set_loading(True)
        self._start_auth_thread(account, password)

    def _emit_logout(self) -> None:
        if self._auth_thread and self._auth_thread.isRunning():
            self.set_status_message("正在注销，请等待当前登录流程结束…")
            return
        self.reset()
        self.logoutRequested.emit()

    # ------------------------------ internals ------------------------------
    def _start_auth_thread(self, account: str, password: str) -> None:
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
        logging.info(
            "CompanyLoginPage: 登录完成 success=%s message=%s payload=%s",
            success,
            message,
            payload,
        )
        self.set_login_result(success, message, payload)

    def _clear_auth_thread(self) -> None:
        self._auth_thread = None
        self._auth_worker = None
