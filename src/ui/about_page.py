#!/usr/bin/env python
# encoding: utf-8

from __future__ import annotations

import os

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
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
from .theme import apply_theme, apply_font_and_selection, FONT_FAMILY


class AboutPage(CardWidget):
    """展示版本与构建信息的页面"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aboutPage")
        apply_theme(self)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = StrongBodyLabel("About")
        apply_theme(title)
        title.setStyleSheet(
            "border-left: 4px solid #0067c0; padding-left: 8px;"
            f" font-family: {FONT_FAMILY};"
        )
        layout.addWidget(title)

        self.info_table = QTableWidget(0, 2, self)
        self.info_table.setHorizontalHeaderLabels(["字段", "信息"])
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.setEditTriggers(self.info_table.NoEditTriggers)
        self.info_table.setSelectionMode(self.info_table.NoSelection)
        self.info_table.horizontalHeader().setStretchLastSection(True)
        apply_theme(self.info_table)
        apply_font_and_selection(self.info_table)
        layout.addWidget(self.info_table)

        self.source_label = QLabel("数据来源：未知", self)
        apply_theme(self.source_label)
        layout.addWidget(self.source_label)

        self.resources_card = CardWidget(self)
        apply_theme(self.resources_card)
        resources_layout = QVBoxLayout(self.resources_card)
        resources_layout.setSpacing(8)

        resource_title = StrongBodyLabel("资源与支持")
        apply_theme(resource_title)
        resource_title.setStyleSheet(
            "border-left: 4px solid #0067c0; padding-left: 8px;"
            f" font-family: {FONT_FAMILY};"
        )
        resources_layout.addWidget(resource_title)

        config_layout = QHBoxLayout()
        config_layout.setSpacing(6)
        open_config_btn = PushButton("打开 config 目录", self.resources_card)
        open_config_btn.clicked.connect(lambda: self._open_path(Paths.CONFIG_DIR))
        config_layout.addWidget(open_config_btn)

        open_res_btn = PushButton("打开 res 目录", self.resources_card)
        open_res_btn.clicked.connect(lambda: self._open_path(Paths.RES_DIR))
        config_layout.addWidget(open_res_btn)
        config_layout.addStretch(1)
        resources_layout.addLayout(config_layout)

        config_files_layout = QHBoxLayout()
        config_files_layout.setSpacing(6)
        for file_name in ("config.yaml", "tool_config.yaml", "compatibility_dut.json"):
            btn = PushButton(file_name, self.resources_card)
            btn.clicked.connect(lambda _, name=file_name: self._open_path(os.path.join(Paths.CONFIG_DIR, name)))
            config_files_layout.addWidget(btn)
        config_files_layout.addStretch(1)
        resources_layout.addLayout(config_files_layout)

        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(6)
        for tool in ("ADBKeyboard.apk", "iperf3", "script"):
            btn = PushButton(tool, self.resources_card)
            btn.clicked.connect(lambda _, name=tool: self._open_path(os.path.join(Paths.RES_DIR, name)))
            tools_layout.addWidget(btn)
        tools_layout.addStretch(1)
        resources_layout.addLayout(tools_layout)

        support_layout = QHBoxLayout()
        support_layout.setSpacing(6)
        email_btn = PushButton("联系维护者", self.resources_card)
        email_btn.clicked.connect(self._show_support_email)
        support_layout.addWidget(email_btn)

        ticket_btn = PushButton("提交工单", self.resources_card)
        ticket_btn.clicked.connect(self._open_ticket_portal)
        support_layout.addWidget(ticket_btn)

        doc_btn = HyperlinkButton("内部文档", self.resources_card)
        doc_btn.clicked.connect(self._open_internal_doc)
        support_layout.addWidget(doc_btn)
        support_layout.addStretch(1)
        resources_layout.addLayout(support_layout)

        compliance_label = QLabel(
            "仅限内部使用：请遵循数据采集、传输与存储合规要求，敏感日志需按流程加密并在 30 天内清理。",
            self.resources_card,
        )
        compliance_label.setWordWrap(True)
        apply_theme(compliance_label)
        resources_layout.addWidget(compliance_label)

        hint_label = QLabel("更多规范详见企业内网《无线测试数据合规手册》。", self.resources_card)
        hint_label.setWordWrap(True)
        apply_theme(hint_label)
        resources_layout.addWidget(hint_label)

        layout.addWidget(self.resources_card)

        layout.addStretch(1)

        self._populate_metadata()

    def _open_path(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _show_support_email(self) -> None:
        QMessageBox.information(
            self,
            "维护者联系方式",
            "如需支持，请联系测试平台维护者：qa-support@example.com",
        )

    def _open_ticket_portal(self) -> None:
        QDesktopServices.openUrl(QUrl("https://intranet.example.com/support/tickets"))

    def _open_internal_doc(self) -> None:
        QDesktopServices.openUrl(QUrl("https://intranet.example.com/docs/wifi-compliance"))

    def _populate_metadata(self) -> None:
        metadata = get_build_metadata()
        display_rows = [
            ("应用名称", metadata.get("package_name", "未知")),
            ("版本", metadata.get("version", "未知")),
            ("构建时间", metadata.get("build_time", "未知")),
            ("Git 分支", metadata.get("branch", "未知")),
            ("提交哈希", metadata.get("commit_hash", "未知")),
            ("提交短哈希", metadata.get("commit_short", "未知")),
            ("提交作者", metadata.get("commit_author", "未知")),
            ("提交时间", metadata.get("commit_date", "未知")),
        ]

        self.info_table.setRowCount(len(display_rows))
        for row, (label, value) in enumerate(display_rows):
            key_item = QTableWidgetItem(label)
            value_item = QTableWidgetItem(value or "未知")
            key_item.setFlags(Qt.ItemIsEnabled)
            value_item.setFlags(Qt.ItemIsEnabled)
            self.info_table.setItem(row, 0, key_item)
            self.info_table.setItem(row, 1, value_item)
        self.info_table.resizeColumnsToContents()

        source = metadata.get("data_source", "未知") or "未知"
        self.source_label.setText(f"数据来源：{source}")

