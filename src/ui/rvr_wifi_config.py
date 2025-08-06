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
from PyQt5.QtWidgets import QVBoxLayout, QTableWidgetItem
from qfluentwidgets import (
    CardWidget,
    TableWidget,
    ComboBox,
    LineEdit,
    PushButton,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
)

from src.tools.router_tool.router_factory import get_router


class RvrWifiConfigPage(CardWidget):
    """配置 RVR Wi-Fi 测试参数"""

    def __init__(self):
        super().__init__()
        self.setObjectName("rvrWifiConfigPage")

        # -------------------- paths --------------------
        base = Path.cwd()
        if hasattr(sys, "_MEIPASS"):
            base = Path(sys._MEIPASS)
            if not (base / "config" / "rvr_wifi_setup.csv").exists():
                base = Path.cwd()
        self.csv_path = (base / "config" / "rvr_wifi_setup.csv").resolve()
        self.config_path = (base / "config" / "config.yaml").resolve()

        # -------------------- router options --------------------
        self.router = self._load_router()
        self.headers, self.rows = self._load_csv()

        # -------------------- layout --------------------
        layout = QVBoxLayout(self)
        self.table = TableWidget(self)
        self._init_table()
        layout.addWidget(self.table)

        self.save_btn = PushButton(FluentIcon.SAVE, "保存", self)
        self.save_btn.clicked.connect(self.save_csv)
        layout.addWidget(self.save_btn, alignment=Qt.AlignRight)

    # ------------------------------------------------------------------
    # 初始化
    def _load_router(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            router_name = cfg.get("router", {}).get("name")
            router = get_router(router_name)
        except Exception as e:
            print(f"load router error: {e}")
            router = get_router("asusax86u")  # fallback
        return router

    def _load_csv(self):
        headers = []
        rows: list[dict[str, str]] = []
        if self.csv_path.exists():
            with open(self.csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = [h.strip() for h in reader.fieldnames]
                for row in reader:
                    rows.append({k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()})
        return headers, rows

    # ------------------------------------------------------------------
    # 表格
    def _init_table(self):
        self.table.setRowCount(len(self.rows))
        self.table.setColumnCount(len(self.headers) + 1)
        self.table.setHorizontalHeaderLabels([""] + self.headers)
        self.table.verticalHeader().setVisible(False)

        for r, row in enumerate(self.rows):
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check_item.setCheckState(Qt.Unchecked)
            self.table.setItem(r, 0, check_item)

            for c, header in enumerate(self.headers):
                value = row.get(header, "")
                widget = self._create_widget(header, value, r)
                if widget:
                    self.table.setCellWidget(r, c + 1, widget)
                else:
                    item = QTableWidgetItem(value)
                    if header == "serial":
                        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    self.table.setItem(r, c + 1, item)

    def _create_widget(self, header: str, value: str, row: int):
        if header == "band":
            combo = ComboBox(self.table)
            combo.addItems(getattr(self.router, "BAND_LIST", ["2.4 GHz", "5 GHz"]))
            combo.setCurrentText(value)
            combo.currentTextChanged.connect(lambda text, r=row: self._update_band_dependent(r, text))
            return combo
        elif header == "wireless_mode":
            combo = ComboBox(self.table)
            band = self._band_of_row(row)
            options = getattr(self.router, "WIRELESS_2" if band == "2.4 GHz" else "WIRELESS_5", [])
            combo.addItems(options)
            combo.setCurrentText(value)
            return combo
        elif header == "channel":
            combo = ComboBox(self.table)
            band = self._band_of_row(row)
            options = getattr(self.router, "CHANNEL_2" if band == "2.4 GHz" else "CHANNEL_5", [])
            combo.addItems(options)
            combo.setCurrentText(value)
            return combo
        elif header == "bandwidth":
            combo = ComboBox(self.table)
            band = self._band_of_row(row)
            options = getattr(self.router, "BANDWIDTH_2" if band == "2.4 GHz" else "BANDWIDTH_5", [])
            combo.addItems(options)
            combo.setCurrentText(value)
            return combo
        elif header == "authentication_method":
            combo = ComboBox(self.table)
            combo.addItems(getattr(self.router, "AUTHENTICATION_METHOD", []))
            combo.setCurrentText(value)
            return combo
        elif header in {"ssid", "wpa_passwd", "test_type", "protocol_type", "data_row", "expected_rate"}:
            line = LineEdit(self.table)
            line.setText(value)
            return line
        elif header == "wifi6":
            combo = ComboBox(self.table)
            combo.addItems(["on", "off"])
            combo.setCurrentText(value)
            return combo
        return None

    def _band_of_row(self, row: int) -> str:
        col = self.headers.index("band") + 1
        widget = self.table.cellWidget(row, col)
        if isinstance(widget, ComboBox):
            return widget.currentText()
        item = self.table.item(row, col)
        return item.text() if item else ""

    def _update_band_dependent(self, row: int, band: str):
        mapping = {
            "wireless_mode": "WIRELESS",
            "channel": "CHANNEL",
            "bandwidth": "BANDWIDTH",
        }
        for name, attr in mapping.items():
            col = self.headers.index(name) + 1
            widget = self.table.cellWidget(row, col)
            if isinstance(widget, ComboBox):
                widget.blockSignals(True)
                widget.clear()
                options = getattr(self.router, f"{attr}_2" if band == "2.4 GHz" else f"{attr}_5", [])
                widget.addItems(options)
                widget.blockSignals(False)

    # ------------------------------------------------------------------
    # 保存
    def save_csv(self):
        data = []
        for r in range(self.table.rowCount()):
            row_data = {}
            for c, header in enumerate(self.headers):
                cell = self.table.cellWidget(r, c + 1)
                if isinstance(cell, ComboBox):
                    text = cell.currentText()
                elif isinstance(cell, LineEdit):
                    text = cell.text()
                else:
                    item = self.table.item(r, c + 1)
                    text = item.text() if item else ""
                row_data[header] = text
            data.append(row_data)
        try:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(data)
            InfoBar.success(title="提示", content="保存成功", parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error(title="错误", content=str(e), parent=self, position=InfoBarPosition.TOP)

