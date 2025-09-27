#!/usr/bin/env python
# encoding: utf-8

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

from src.util.constants import get_build_metadata, Paths
from .theme import (
    apply_theme,
    apply_font_and_selection,
    FONT_FAMILY,
    FONT_SIZE,
    STYLE_BASE,
    TEXT_COLOR,
)


class AboutPage(CardWidget):
    """展示版本与构建信息的页面"""

    def __init__(self, parent: QWidget | None = None) -> None:
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
            border-left: 4px solid #0067c0;
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
            border-left: 4px solid #0067c0;
            padding-left: 8px;
            """
        )
        resource_title.setFont(base_font)
        resources_layout.addWidget(resource_title)

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

        config_files_layout = QHBoxLayout()
        config_files_layout.setSpacing(6)
        for file_name in ("config.yaml", "tool_config.yaml", "compatibility_dut.json"):
            btn = PushButton(file_name, self.resources_card)
            btn.clicked.connect(lambda _, name=file_name: self._open_path(os.path.join(Paths.CONFIG_DIR, name)))
            btn.setFont(base_font)
            config_files_layout.addWidget(btn)
        config_files_layout.addStretch(1)
        resources_layout.addLayout(config_files_layout)

        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(6)
        for tool in ("ADBKeyboard.apk", "iperf3", "script"):
            btn = PushButton(tool, self.resources_card)
            btn.clicked.connect(lambda _, name=tool: self._open_path(os.path.join(Paths.RES_DIR, name)))
            btn.setFont(base_font)
            tools_layout.addWidget(btn)
        tools_layout.addStretch(1)
        resources_layout.addLayout(tools_layout)

        support_layout = QHBoxLayout()
        support_layout.setSpacing(6)
        email_btn = PushButton("Contact Maintainer", self.resources_card)
        email_btn.clicked.connect(self._show_support_email)
        email_btn.setFont(base_font)
        support_layout.addWidget(email_btn)

        ticket_btn = PushButton("Submit Ticket", self.resources_card)
        ticket_btn.clicked.connect(self._open_ticket_portal)
        ticket_btn.setFont(base_font)
        support_layout.addWidget(ticket_btn)

        doc_btn = HyperlinkButton(
            "https://intranet.example.com/docs/wifi-compliance",
            "Internal Documentation",
            self.resources_card,
        )
        doc_btn.clicked.connect(self._open_internal_doc)
        doc_btn.setFont(base_font)
        support_layout.addWidget(doc_btn)
        support_layout.addStretch(1)
        resources_layout.addLayout(support_layout)

        compliance_label = QLabel(
            "Internal use only: Follow data collection, transfer, and storage compliance policies."
            " Encrypt sensitive logs as required and purge them within 30 days.",
            self.resources_card,
        )
        compliance_label.setWordWrap(True)
        apply_theme(compliance_label)
        compliance_label.setFont(base_font)
        resources_layout.addWidget(compliance_label)

        hint_label = QLabel(
            "Refer to the corporate intranet Wireless Testing Data Compliance Manual for more guidance.",
            self.resources_card,
        )
        hint_label.setWordWrap(True)
        apply_theme(hint_label)
        hint_label.setFont(base_font)
        resources_layout.addWidget(hint_label)

        layout.addWidget(self.resources_card)

        layout.addStretch(1)

        self._populate_metadata()

    def _open_path(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _show_support_email(self) -> None:
        QMessageBox.information(
            self,
            "Maintainer Contact",
            "For assistance, contact the testing platform maintainer: qa-support@example.com",
        )

    def _open_ticket_portal(self) -> None:
        QDesktopServices.openUrl(QUrl("https://intranet.example.com/support/tickets"))

    def _open_internal_doc(self) -> None:
        QDesktopServices.openUrl(QUrl("https://intranet.example.com/docs/wifi-compliance"))

    def _populate_metadata(self) -> None:
        metadata = get_build_metadata()
        latest_version = self._get_latest_version_from_changelog(metadata)
        display_rows = [
            ("Application Name", metadata.get("package_name", "Unknown")),
            ("Version", latest_version or "Unknown"),
            ("Build Time", metadata.get("build_time", "Unknown")),
            ("Git Branch", metadata.get("branch", "Unknown")),
            ("Commit Hash", metadata.get("commit_hash", "Unknown")),
            ("Commit Short Hash", metadata.get("commit_short", "Unknown")),
            ("Commit Author", metadata.get("commit_author", "Unknown")),
            ("Commit Date", metadata.get("commit_date", "Unknown")),
            ("Author", "chao.li"),
            ("Acknowledgements", "zijie.chen, yifeng.xu, meng.wang1"),
        ]

        self.info_table.setRowCount(len(display_rows))
        for row, (label, value) in enumerate(display_rows):
            key_item = QTableWidgetItem(label)
            if not isinstance(value, str):
                value = str(value) if value is not None else ""
            value_item = QTableWidgetItem(value.strip() or "Unknown")
            key_item.setFlags(Qt.ItemIsEnabled)
            value_item.setFlags(Qt.ItemIsEnabled)
            self.info_table.setItem(row, 0, key_item)
            self.info_table.setItem(row, 1, value_item)
        self.info_table.resizeColumnsToContents()

        source = metadata.get("data_source", "Unknown") or "Unknown"
        source = source.replace("、", ", ")
        source = source.replace("，", ", ")
        source = source.replace("缓存", "Cache")
        source = source.replace("未知", "Unknown")
        source = re.sub(r"\s*,\s*", ", ", source)
        source = re.sub(r"\s+", " ", source).strip()
        self.source_label.setText(f"Data Source: {source}")

    def _get_latest_version_from_changelog(self, metadata: dict[str, str]) -> str:
        default_version = metadata.get("version") or "Unknown"
        readme_path = Path(Paths.BASE_DIR) / "README.md"
        try:
            content = readme_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return default_version

        lines = content.splitlines()
        in_changelog = False
        latest_entry: str | None = None
        for line in lines:
            stripped = line.strip()
            if not in_changelog:
                if stripped.lower().startswith("## changelog"):
                    in_changelog = True
                continue
            if stripped.startswith("## ") and not stripped.lower().startswith("## changelog"):
                break
            if stripped:
                latest_entry = stripped

        if not latest_entry:
            return default_version or "Unknown"

        match = re.search(r"v\s*[0-9][\w.]*", latest_entry, re.IGNORECASE)
        if match:
            return match.group(0).replace(" ", "")

        return latest_entry or (default_version or "Unknown")

