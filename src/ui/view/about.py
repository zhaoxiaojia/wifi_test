"""View module for the About sidebar page.

This module contains the *pure UI* for the About/Help page:

- Title label
- Information table (app name, version, build time, etc.)
- Data source label
- Resources card with directory shortcuts, frequently used config file shortcuts,
  support links, and compliance hints.

All behaviour (reading metadata, opening paths, external links) is implemented
in :mod:`about_page` which composes this view and wires signals.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)
from qfluentwidgets import CardWidget, StrongBodyLabel, PushButton

from src.ui.view.theme import (
    ACCENT_COLOR,
    FONT_FAMILY,
    FONT_SIZE,
    STYLE_BASE,
    TEXT_COLOR,
    apply_theme,
    apply_font_and_selection,
)


class AboutView(CardWidget):
    """Pure UI view for the About page (no file system or browser logic)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aboutView")
        apply_theme(self, recursive=True)

        base_font = QFont(FONT_FAMILY, FONT_SIZE)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Page title
        self.title_label = StrongBodyLabel("About", self)
        apply_theme(self.title_label)
        self.title_label.setStyleSheet(
            f"""
            {STYLE_BASE} color:{TEXT_COLOR};
            border-left: 4px solid {ACCENT_COLOR};
            padding-left: 8px;
            """
        )
        self.title_label.setFont(base_font)
        layout.addWidget(self.title_label)

        # Metadata table
        self.info_table = QTableWidget(0, 2, self)
        self.info_table.setHorizontalHeaderLabels(["Field", "Details"])
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.setEditTriggers(self.info_table.NoEditTriggers)
        self.info_table.setSelectionMode(self.info_table.NoSelection)
        self.info_table.horizontalHeader().setStretchLastSection(True)
        apply_theme(self.info_table)
        apply_font_and_selection(self.info_table)
        self.info_table.setFont(base_font)
        layout.addWidget(self.info_table)

        # Data source label
        self.source_label = QLabel("Data Source: Unknown", self)
        apply_theme(self.source_label)
        self.source_label.setFont(base_font)
        layout.addWidget(self.source_label)

        # Resources card
        self.resources_card = CardWidget(self)
        apply_theme(self.resources_card)
        self.resources_card.setFont(base_font)
        resources_layout = QVBoxLayout(self.resources_card)
        resources_layout.setSpacing(8)

        # Resources title
        self.resource_title_label = StrongBodyLabel("Resources & Support", self.resources_card)
        apply_theme(self.resource_title_label)
        self.resource_title_label.setStyleSheet(
            f"""
            {STYLE_BASE} color:{TEXT_COLOR};
            border-left: 4px solid {ACCENT_COLOR};
            padding-left: 8px;
            """
        )
        self.resource_title_label.setFont(base_font)
        resources_layout.addWidget(self.resource_title_label)

        # Directory shortcuts
        config_layout = QHBoxLayout()
        config_layout.setSpacing(6)
        self.open_config_btn = PushButton("Open config directory", self.resources_card)
        self.open_config_btn.setFont(base_font)
        config_layout.addWidget(self.open_config_btn)

        self.open_res_btn = PushButton("Open res directory", self.resources_card)
        self.open_res_btn.setFont(base_font)
        config_layout.addWidget(self.open_res_btn)
        config_layout.addStretch(1)
        resources_layout.addLayout(config_layout)

        # Frequently used config files: one-click open
        config_files_layout = QHBoxLayout()
        config_files_layout.setSpacing(6)
        self.config_file_buttons: list[PushButton] = []
        for file_name in ("config_basic.yaml", "config_performance.yaml", "config_tool.yaml", "compatibility_dut.json"):
            btn = PushButton(file_name, self.resources_card)
            btn.setFont(base_font)
            # Store the file name as a property for the controller to read.
            btn.setProperty("configFileName", file_name)
            self.config_file_buttons.append(btn)
            config_files_layout.addWidget(btn)
        config_files_layout.addStretch(1)
        resources_layout.addLayout(config_files_layout)

        # Support & documentation: maintainer / Jira / internal docs
        support_layout = QHBoxLayout()
        support_layout.setSpacing(6)
        self.email_btn = PushButton("Contact Maintainer", self.resources_card)
        self.email_btn.setFont(base_font)
        support_layout.addWidget(self.email_btn)

        self.jira_btn = PushButton("Jira Submit", self.resources_card)
        self.jira_btn.setFont(base_font)
        support_layout.addWidget(self.jira_btn)

        self.doc_btn = PushButton("Internal Documentation", self.resources_card)
        self.doc_btn.setFont(base_font)
        support_layout.addWidget(self.doc_btn)
        support_layout.addStretch(1)
        resources_layout.addLayout(support_layout)

        # Compliance reminder
        self.compliance_label = QLabel(
            "Internal use only: Follow data collection, transfer, and storage compliance policies. "
            "Encrypt sensitive logs when required and purge them within 30 days.",
            self.resources_card,
        )
        self.compliance_label.setWordWrap(True)
        apply_theme(self.compliance_label)
        self.compliance_label.setFont(base_font)
        resources_layout.addWidget(self.compliance_label)

        self.hint_label = QLabel(
            "For more details, see the corporate intranet Wireless Testing Data Compliance Manual.",
            self.resources_card,
        )
        self.hint_label.setWordWrap(True)
        apply_theme(self.hint_label)
        self.hint_label.setFont(base_font)
        resources_layout.addWidget(self.hint_label)

        layout.addWidget(self.resources_card)
        layout.addStretch(1)

        # Logical control map for the about page.
        # Keys follow: page_frame_group_purpose_type
        self.about_controls: dict[str, object] = {
            "about_main_title_label": self.title_label,
            "about_main_info_table": self.info_table,
            "about_main_source_label": self.source_label,
            "about_main_resources_card": self.resources_card,
            "about_main_resources_title_label": self.resource_title_label,
            "about_main_resources_open_config_btn": self.open_config_btn,
            "about_main_resources_open_res_btn": self.open_res_btn,
            "about_main_resources_compliance_label": self.compliance_label,
            "about_main_resources_hint_label": self.hint_label,
        }
