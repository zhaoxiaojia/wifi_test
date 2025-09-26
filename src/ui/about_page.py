#!/usr/bin/env python
# encoding: utf-8

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)
from qfluentwidgets import CardWidget, StrongBodyLabel

from src.util.constants import get_build_metadata
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

        layout.addStretch(1)

        self._populate_metadata()

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

