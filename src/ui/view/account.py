"""Account (login) page UI view.

This module hosts the *pure UI* for the company account sign‑in page.
Business logic (LDAP authentication, threading, etc.) remains in
``company_login.py`` which composes this view and wires signals.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
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

