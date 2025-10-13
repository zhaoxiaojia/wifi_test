#!/usr/bin/env python
# encoding: utf-8
"""登录页面，提供微软 Teams 凭据输入与登录状态管理"""
from __future__ import annotations

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
from qfluentwidgets import LineEdit, PushButton, FluentIcon

from src.util.constants import FONT_FAMILY
from .theme import apply_theme


class TeamsLoginPage(QWidget):
    """简单的 Teams 登录页，收集账号信息并对外暴露登录相关信号"""

    loginRequested = pyqtSignal(str, str)
    """当用户点击登录按钮时发出 (account, password)"""

    loginResult = pyqtSignal(bool, str)
    """登录完成后发出 (success, message)"""

    logoutRequested = pyqtSignal()
    """用户点击注销按钮时发出"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("teamsLoginPage")
        self._loading = False
        self._logged_in = False
        apply_theme(self, recursive=True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(120, 80, 120, 80)
        main_layout.setSpacing(24)
        main_layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Teams 登录", self)
        title_font = QFont(FONT_FAMILY, 24)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        form_widget = QWidget(self)
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(16)
        form_layout.setContentsMargins(0, 0, 0, 0)

        self.account_edit = LineEdit(form_widget)
        self.account_edit.setPlaceholderText("账号，例如 your.name@example.com")
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

    def set_login_result(self, success: bool, message: str = "") -> None:
        """更新登录状态并对外广播结果"""
        self._logged_in = success
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
        self.loginResult.emit(success, message)

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
        account = self.account_edit.text().strip()
        password = self.password_edit.text()
        self.set_status_message("正在发起登录请求，请稍候…")
        self.set_loading(True)
        self.loginRequested.emit(account, password)

    def _emit_logout(self) -> None:
        self.reset()
        self.logoutRequested.emit()
