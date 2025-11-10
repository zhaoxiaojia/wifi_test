#!/usr/bin/env python
# encoding: utf-8
"""
About page for the Wi‑Fi Test Tool GUI.

This module defines a Qt-based page that presents build/version metadata,
quick links to local configuration folders and frequently used config files,
and internal support resources (email / Jira / Confluence).

Goals
-----
- Centralize **diagnostic context** (version, build time, data source) for both users and maintainers.
- Offer **single-click access** to config directories and key files to reduce support effort.
- Encourage **compliance** by surfacing policy reminders in the UI.

Typical usage
-------------
The page is embedded inside the main FluentWindow navigation stack:

>>> page = AboutPage(parent=window)
>>> window.addSubInterface(page, icon=..., text="About")

Notes
-----
This page reads project metadata via :func:`src.util.constants.get_build_metadata` and
optionally parses the latest version and acknowledgements from a local README.md.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
    QMessageBox,
    QHBoxLayout,
)
from qfluentwidgets import CardWidget, StrongBodyLabel, PushButton, HyperlinkButton

from src.util.constants import Paths, get_build_metadata
from .theme import (
    ACCENT_COLOR,
    FONT_FAMILY,
    FONT_SIZE,
    STYLE_BASE,
    TEXT_COLOR,
    apply_theme,
    apply_font_and_selection,
)
from .style import (
    acknowledgements_from_readme,
    latest_version_from_changelog,
    normalize_data_source_label,
)


class AboutPage(CardWidget):
    """
    The “About / Help” page. Displays build & version info, plus resource and support entry points.

    UI structure
    ------------
    - Title section (StrongBodyLabel)
    - Info table (key/value): app name, version, build time, author, acknowledgements
    - Data source label
    - Resources card (CardWidget)
        * Quick directory buttons (config directory / res directory)
        * One-click open for frequently used config files (e.g., config_dut.yaml)
        * Support & documentation (maintainer email, Jira, internal docs)
        * Compliance reminder (e.g., encryption / retention)

    Parameters
    ----------
    parent : QWidget | None
        Parent widget. Used for theme/typography inheritance and window hierarchy.

    Notes
    -----
    - All visible widgets adopt a unified theme and font (see ``theme.py``).
    - The second table column stretches to fit content to avoid truncation.
    - The page performs no network I/O; external links open in the system browser.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize widgets, set up layouts, and populate metadata into the table and labels."""
        super().__init__(parent)
        self.setObjectName("aboutPage")
        apply_theme(self, recursive=True)
        base_font = QFont(FONT_FAMILY, FONT_SIZE)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = StrongBodyLabel("About")
        apply_theme(title)
        title.setStyleSheet(
            f"""
            {STYLE_BASE} color:{TEXT_COLOR};
            border-left: 4px solid {ACCENT_COLOR};
            padding-left: 8px;
            """
        )
        title.setFont(base_font)
        layout.addWidget(title)

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

        self.source_label = QLabel("Data Source: Unknown", self)
        apply_theme(self.source_label)
        self.source_label.setFont(base_font)
        layout.addWidget(self.source_label)

        self.resources_card = CardWidget(self)
        apply_theme(self.resources_card)
        self.resources_card.setFont(base_font)
        resources_layout = QVBoxLayout(self.resources_card)
        resources_layout.setSpacing(8)

        resource_title = StrongBodyLabel("Resources & Support")
        apply_theme(resource_title)
        resource_title.setStyleSheet(
            f"""
            {STYLE_BASE} color:{TEXT_COLOR};
            border-left: 4px solid {ACCENT_COLOR};
            padding-left: 8px;
            """
        )
        resource_title.setFont(base_font)
        resources_layout.addWidget(resource_title)

        # Directory shortcuts
        config_layout = QHBoxLayout()
        config_layout.setSpacing(6)
        open_config_btn = PushButton("Open config directory", self.resources_card)
        open_config_btn.clicked.connect(lambda: self._open_path(Paths.CONFIG_DIR))
        open_config_btn.setFont(base_font)
        config_layout.addWidget(open_config_btn)

        open_res_btn = PushButton("Open res directory", self.resources_card)
        open_res_btn.clicked.connect(lambda: self._open_path(Paths.RES_DIR))
        open_res_btn.setFont(base_font)
        config_layout.addWidget(open_res_btn)
        config_layout.addStretch(1)
        resources_layout.addLayout(config_layout)

        # Frequently used config files: one-click open
        config_files_layout = QHBoxLayout()
        config_files_layout.setSpacing(6)
        for file_name in ("config_dut.yaml", "config_execution.yaml", "config_tool.yaml", "compatibility_dut.json"):
            btn = PushButton(file_name, self.resources_card)
            btn.clicked.connect(lambda _, name=file_name: self._open_path(os.path.join(Paths.CONFIG_DIR, name)))
            btn.setFont(base_font)
            config_files_layout.addWidget(btn)
        config_files_layout.addStretch(1)
        resources_layout.addLayout(config_files_layout)

        # Support & documentation: maintainer / Jira / internal docs
        support_layout = QHBoxLayout()
        support_layout.setSpacing(6)
        email_btn = PushButton("Contact Maintainer", self.resources_card)
        email_btn.clicked.connect(self._show_support_email)
        email_btn.setFont(base_font)
        support_layout.addWidget(email_btn)

        jira_btn = PushButton("Jira Submit", self.resources_card)
        jira_btn.clicked.connect(self._open_ticket_portal)
        jira_btn.setFont(base_font)
        support_layout.addWidget(jira_btn)

        doc_btn = PushButton("Internal Documentation", self.resources_card)
        doc_btn.clicked.connect(self._open_internal_doc)
        doc_btn.setFont(base_font)
        support_layout.addWidget(doc_btn)
        support_layout.addStretch(1)
        resources_layout.addLayout(support_layout)

        # Compliance reminder
        compliance_label = QLabel(
            "Internal use only: Follow data collection, transfer, and storage compliance policies. "
            "Encrypt sensitive logs when required and purge them within 30 days.",
            self.resources_card,
        )
        compliance_label.setWordWrap(True)
        apply_theme(compliance_label)
        compliance_label.setFont(base_font)
        resources_layout.addWidget(compliance_label)

        hint_label = QLabel(
            "For more details, see the corporate intranet Wireless Testing Data Compliance Manual.",
            self.resources_card,
        )
        hint_label.setWordWrap(True)
        apply_theme(hint_label)
        hint_label.setFont(base_font)
        resources_layout.addWidget(hint_label)

        layout.addWidget(self.resources_card)
        layout.addStretch(1)

        self._populate_metadata()

    # ---------------------------------------------------------------------
    # Helpers / Actions
    # ---------------------------------------------------------------------

    def _open_path(self, path: str) -> None:
        """
        Open a local path in the OS file manager.

        Parameters
        ----------
        path : str
            Target file or directory path, absolute or relative.

        Side Effects
        ------------
        Calls :class:`QDesktopServices` to invoke an external program (platform-dependent).
        """
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _show_support_email(self) -> None:
        """
        Show a dialog containing the maintainer's contact email.

        Notes
        -----
        - This method does not send an actual email.
        - Users compose and send messages via their own mail client.
        """
        QMessageBox.information(
            self,
            "Maintainer Contact",
            "For assistance, contact the testing platform maintainer: chao.li@amlogic.com",
        )

    def _open_ticket_portal(self) -> None:
        """
        Open the Jira submission portal in the default browser.

        Side Effects
        ------------
        Uses :class:`QDesktopServices` to open an external URL.
        """
        QDesktopServices.openUrl(QUrl("https://jira.amlogic.com/browse/FQ-383"))

    def _open_internal_doc(self) -> None:
        """
        Open internal documentation (Confluence) in the default browser.

        Security
        --------
        Access requires corporate intranet permissions; it is not reachable externally.
        """
        QDesktopServices.openUrl(QUrl("https://confluence.amlogic.com/pages/viewpage.action?pageId=448826402"))

    def _populate_metadata(self) -> None:
        """
        Read/normalize build metadata and fill the info table and “Data Source” label.

        Pipeline
        --------
        1. Read metadata via :func:`get_build_metadata`.
        2. Parse the latest version from README.md (if available).
        3. Parse acknowledgements from README.md (if available).
        4. Fill the QTableWidget; normalize and display the data source string.

        Notes
        -----
        - Values are safely cast to strings and stripped; empty values fallback to ``"Unknown"``.
        - The “Data Source” string collapses excessive spaces and converts Chinese punctuation to English commas.
        """
        metadata = get_build_metadata()
        latest_version = latest_version_from_changelog(metadata)
        acknowledgements = acknowledgements_from_readme()

        display_rows = [
            ("Application Name", metadata.get("package_name", "Unknown")),
            ("Version", latest_version or "Unknown"),
            ("Build Time", metadata.get("build_time", "Unknown")),
            ("Author", "chao.li"),
            ("Acknowledgements", acknowledgements if acknowledgements else "Unknown"),
        ]

        self.info_table.setRowCount(len(display_rows))
        for row, (label, value) in enumerate(display_rows):
            key_item = QTableWidgetItem(label)
            if not isinstance(value, str):
                value = str(value) if value is not None else ""
            value_item = QTableWidgetItem((value or "").strip() or "Unknown")
            key_item.setFlags(Qt.ItemIsEnabled)
            value_item.setFlags(Qt.ItemIsEnabled)
            self.info_table.setItem(row, 0, key_item)
            self.info_table.setItem(row, 1, value_item)
        self.info_table.resizeColumnsToContents()

        source = metadata.get("data_source", "Unknown") or "Unknown"
        self.source_label.setText(f"Data Source: {normalize_data_source_label(source)}")

