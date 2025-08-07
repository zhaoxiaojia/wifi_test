#!/usr/bin/env python
# encoding: utf-8
"""
RVR Wi-Fi configuration page
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import yaml
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QTableWidgetItem,
    QGroupBox,
    QFormLayout,
    QWidget,
    QCheckBox,
    QAbstractItemView,
    QHeaderView,
)
from qfluentwidgets import (
    CardWidget,
    TableWidget,
    ComboBox,
    LineEdit,
    PushButton,
    InfoBar,
    InfoBarPosition,
)

from src.tools.router_tool.router_factory import get_router
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .windows_case_config import CaseConfigPage


class WifiTableWidget(TableWidget):
    """支持拖拽排序并通知父页面同步行顺序的表格"""

    def __init__(self, page: "RvrWifiConfigPage"):
        super().__init__(page)
        self.page = page
        # 仅允许单行选择并整行高亮
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        # 垂直表头允许拖动以调整行顺序
        vh = self.verticalHeader()
        vh.setVisible(True)
        vh.setSectionsMovable(True)
        vh.sectionMoved.connect(lambda *_: self.page._sync_rows())
        # 启用内部拖拽排序
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)

    # 仍保留 dropEvent 以兼容内部拖拽
    def dropEvent(self, event):  # type: ignore[override]
        super().dropEvent(event)
        self.page._sync_rows()


class RvrWifiConfigPage(CardWidget):
    """配置 RVR Wi-Fi 测试参数"""

    def __init__(self, case_config_page: "CaseConfigPage"):
        super().__init__()
        self.setObjectName("rvrWifiConfigPage")
        self.case_config_page = case_config_page

        base = Path.cwd()
        if hasattr(sys, "_MEIPASS"):
            base = Path(sys._MEIPASS)
            if not (base / "config" / "rvr_wifi_setup.csv").exists():
                base = Path.cwd()
        self.csv_path = (base / "config" / "rvr_wifi_setup.csv").resolve()
        self.config_path = (base / "config" / "config.yaml").resolve()

        self.router, self.router_name = self._load_router()

        self.headers, self.rows = self._load_csv()

        main_layout = QHBoxLayout(self)

        form_box = QGroupBox(self)
        form_layout = QFormLayout(form_box)
        self.band_combo = ComboBox(form_box)
        band_list = getattr(self.router, "BAND_LIST", ["2.4 GHz", "5 GHz"])
        self.band_combo.addItems(band_list)
        form_layout.addRow("band", self.band_combo)

        self.wireless_combo = ComboBox(form_box)
        form_layout.addRow("wireless_mode", self.wireless_combo)

        self.channel_combo = ComboBox(form_box)
        form_layout.addRow("channel", self.channel_combo)

        self.bandwidth_combo = ComboBox(form_box)
        form_layout.addRow("bandwidth", self.bandwidth_combo)

        self.auth_combo = ComboBox(form_box)
        self.auth_combo.addItems(getattr(self.router, "AUTHENTICATION_METHOD", []))
        form_layout.addRow("authentication", self.auth_combo)

        test_widget = QWidget(form_box)
        test_layout = QHBoxLayout(test_widget)
        test_layout.setContentsMargins(0, 0, 0, 0)
        self.tx_check = QCheckBox("tx", test_widget)
        self.rx_check = QCheckBox("rx", test_widget)
        test_layout.addWidget(self.tx_check)
        test_layout.addWidget(self.rx_check)
        form_layout.addRow("test_type", test_widget)

        self.data_row_edit = LineEdit(form_box)
        form_layout.addRow("data_row", self.data_row_edit)

        self.expected_rate_tx_edit = LineEdit(form_box)
        form_layout.addRow("expected_rate_tx", self.expected_rate_tx_edit)

        self.expected_rate_rx_edit = LineEdit(form_box)
        form_layout.addRow("expected_rate_rx", self.expected_rate_rx_edit)

        btn_widget = QWidget(form_box)
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.add_btn = PushButton("添加", btn_widget)
        self.add_btn.clicked.connect(self.add_row)
        btn_layout.addWidget(self.add_btn)
        self.del_btn = PushButton("删除", btn_widget)
        self.del_btn.clicked.connect(self.delete_row)
        btn_layout.addWidget(self.del_btn)
        self.save_btn = PushButton("保存", btn_widget)
        self.save_btn.clicked.connect(self.save_csv)
        btn_layout.addWidget(self.save_btn)
        form_layout.addRow(btn_widget)

        main_layout.addWidget(form_box, 1)

        self.table = WifiTableWidget(self)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setStretchLastSection(True)
        main_layout.addWidget(self.table, 2)

        self.band_combo.currentTextChanged.connect(self._update_band_options)
        self.wireless_combo.currentTextChanged.connect(self._update_auth_options)
        self._update_band_options(self.band_combo.currentText())
        self._update_auth_options(self.wireless_combo.currentText())

        self.refresh_table()

        # 监听主配置页面的路由器信息变化
        self.case_config_page.routerInfoChanged.connect(self.reload_router)

    # ------------------------------------------------------------------
    def _load_router(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            router_name = cfg.get("router", {}).get("name")
            router = get_router(router_name)
        except Exception as e:
            print(f"load router error: {e}")
            router_name = "asusax86u"
            router = get_router(router_name)
        return router, router_name

    def _load_csv(self):
        headers = [
            "band",
            "wireless_mode",
            "channel",
            "bandwidth",
            "authentication",
            "tx",
            "rx",
            "data_row",
            "expected_rate_tx",
            "expected_rate_rx",
        ]
        rows: list[dict[str, str]] = []
        if self.csv_path.exists():
            with open(self.csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append({h: row.get(h, "") for h in headers})
        return headers, rows

    def reload_router(self):
        """重新加载路由器配置并刷新频段相关选项"""
        name = ""
        combo = getattr(self.case_config_page, "router_name_combo", None)
        if combo is not None:
            name = combo.currentText()
        else:
            cfg = getattr(self.case_config_page, "config", {})
            if isinstance(cfg, dict):
                name = cfg.get("router", {}).get("name", self.router_name)
        try:
            self.router = get_router(name)
            self.router_name = name
        except Exception as e:
            print(f"reload router error: {e}")
            return

        band_list = getattr(self.router, "BAND_LIST", ["2.4 GHz", "5 GHz"])
        current_band = self.band_combo.currentText()
        if current_band not in band_list:
            current_band = band_list[0] if band_list else ""

        self.band_combo.blockSignals(True)
        self.band_combo.clear()
        self.band_combo.addItems(band_list)
        if current_band:
            self.band_combo.setCurrentText(current_band)
        self.band_combo.blockSignals(False)

        self._update_band_options(current_band)

    def _update_band_options(self, band: str):
        wireless = {"2.4 GHz": getattr(self.router, "WIRELESS_2", []),
                    "5 GHz": getattr(self.router, "WIRELESS_5", [])}[band]
        channel = {"2.4 GHz": getattr(self.router, "CHANNEL_2", []),
                   "5 GHz": getattr(self.router, "CHANNEL_5", [])}[band]
        bandwidth = {"2.4 GHz": getattr(self.router, "BANDWIDTH_2", []),
                     "5 GHz": getattr(self.router, "BANDWIDTH_5", [])}[band]
        self.wireless_combo.clear()
        self.wireless_combo.addItems(wireless)
        self.channel_combo.clear()
        self.channel_combo.addItems(channel)
        self.bandwidth_combo.clear()
        self.bandwidth_combo.addItems(bandwidth)
        self._update_auth_options(self.wireless_combo.currentText())

    def _update_auth_options(self, wireless: str):
        self.auth_combo.clear()
        if "Legacy" in wireless:
            self.auth_combo.addItems(getattr(self.router, "AUTHENTICATION_METHOD_LEGCY", []))
        else:
            self.auth_combo.addItems(getattr(self.router, "AUTHENTICATION_METHOD", []))

    def refresh_table(self):
        self.table.clear()
        self.table.setRowCount(len(self.rows))
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        for r, row in enumerate(self.rows):
            for c, h in enumerate(self.headers):
                item = QTableWidgetItem(str(row.get(h, "")))
                item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(r, c, item)

    def _sync_rows(self):
        self._collect_table_data()

    def _collect_table_data(self):
        data: list[dict[str, str]] = []
        for r in range(self.table.rowCount()):
            row: dict[str, str] = {}
            for c, h in enumerate(self.headers):
                item = self.table.item(r, c)
                row[h] = item.text() if item else ""
            data.append(row)
        self.rows = data

    def add_row(self):
        row = {
            "band": self.band_combo.currentText(),
            "wireless_mode": self.wireless_combo.currentText(),
            "channel": self.channel_combo.currentText(),
            "bandwidth": self.bandwidth_combo.currentText(),
            "authentication": self.auth_combo.currentText(),
            "tx": "1" if self.tx_check.isChecked() else "0",
            "rx": "1" if self.rx_check.isChecked() else "0",
            "data_row": self.data_row_edit.text(),
            "expected_rate_tx": self.expected_rate_tx_edit.text(),
            "expected_rate_rx": self.expected_rate_rx_edit.text(),
        }
        self.rows.append(row)
        self.refresh_table()

    def delete_row(self):
        self._collect_table_data()
        row = self.table.currentRow()
        if 0 <= row < len(self.rows):
            self.rows.pop(row)
            self.refresh_table()

    def save_csv(self):
        self._collect_table_data()
        try:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(self.rows)
            InfoBar.success(title="提示", content="保存成功", parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error(title="错误", content=str(e), parent=self, position=InfoBarPosition.TOP)

