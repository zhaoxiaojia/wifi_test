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

    def __init__(self, ssid_2g: str = "", passwd_2g: str = "", ssid_5g: str = "", passwd_5g: str = ""):
        super().__init__()
        self.setObjectName("rvrWifiConfigPage")
        self.ssid_2g = ssid_2g
        self.passwd_2g = passwd_2g
        self.ssid_5g = ssid_5g
        self.passwd_5g = passwd_5g

        # -------------------- paths --------------------
        base = Path.cwd()
        if hasattr(sys, "_MEIPASS"):
            base = Path(sys._MEIPASS)
            if not (base / "config" / "rvr_wifi_setup.csv").exists():
                base = Path.cwd()
        self.csv_path = (base / "config" / "rvr_wifi_setup.csv").resolve()
        self.config_path = (base / "config" / "config.yaml").resolve()

        # -------------------- router options --------------------
        self.router, self.router_name = self._load_router()
        self.headers, self.rows = self._load_csv()
        self._apply_wifi_info()

        # -------------------- layout --------------------
        layout = QVBoxLayout(self)
        # router selector
        self.router_combo = ComboBox(self)
        self.router_combo.addItems([
            "asusax86u",
            "asusax88u",
            "asusax5400",
            "asusax6700",
            "xiaomiredax6000",
            "xiaomiax3000",
        ])
        self.router_combo.setCurrentText(self.router_name)
        self.router_combo.currentTextChanged.connect(self.set_router)
        layout.addWidget(self.router_combo)

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
            router_name = "asusax86u"
            router = get_router(router_name)  # fallback
        return router, router_name

    def _load_csv(self):
        headers = []
        rows: list[dict[str, str]] = []
        if self.csv_path.exists():
            with open(self.csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = [h.strip() for h in reader.fieldnames if h.strip() != "serial"]
                for row in reader:
                    rows.append(
                        {
                            k.strip(): (v.strip() if isinstance(v, str) else v)
                            for k, v in row.items()
                            if k.strip() != "serial"
                        }
                    )
        return headers, rows

    def _apply_wifi_info(self):
        for row in self.rows:
            band = row.get("band", "")
            if band == "2.4 GHz":
                row["ssid"] = self.ssid_2g
                row["wpa_passwd"] = self.passwd_2g
            elif band == "5 GHz":
                row["ssid"] = self.ssid_5g
                row["wpa_passwd"] = self.passwd_5g

    def update_wifi_info(self, ssid_2g: str, passwd_2g: str, ssid_5g: str, passwd_5g: str):
        self.ssid_2g = ssid_2g
        self.passwd_2g = passwd_2g
        self.ssid_5g = ssid_5g
        self.passwd_5g = passwd_5g
        for r, row in enumerate(self.rows):
            band = row.get("band", "")
            if band == "2.4 GHz":
                row["ssid"] = ssid_2g
                row["wpa_passwd"] = passwd_2g
            elif band == "5 GHz":
                row["ssid"] = ssid_5g
                row["wpa_passwd"] = passwd_5g
            # update widgets
            if "ssid" in self.headers:
                col = self.headers.index("ssid")
                widget = self.table.cellWidget(r, col)
                if isinstance(widget, LineEdit):
                    widget.setText(row["ssid"])
            if "wpa_passwd" in self.headers:
                col = self.headers.index("wpa_passwd")
                widget = self.table.cellWidget(r, col)
                if isinstance(widget, LineEdit):
                    widget.setText(row["wpa_passwd"])

    # ------------------------------------------------------------------
    # 表格
    def _init_table(self):
        self.table.setRowCount(len(self.rows))
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().setVisible(False)

        for r, row in enumerate(self.rows):
            for c, header in enumerate(self.headers):
                value = row.get(header, "")
                widget = self._create_widget(header, value, r)
                if widget:
                    self.table.setCellWidget(r, c, widget)
                else:
                    item = QTableWidgetItem(value)
                    self.table.setItem(r, c, item)

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
            if header in {"ssid", "wpa_passwd"}:
                line.setReadOnly(True)
            return line
        elif header == "wifi6":
            combo = ComboBox(self.table)
            combo.addItems(["on", "off"])
            combo.setCurrentText(value)
            return combo
        return None

    def _band_of_row(self, row: int) -> str:
        col = self.headers.index("band")
        widget = self.table.cellWidget(row, col)
        if isinstance(widget, ComboBox):
            return widget.currentText()
        item = self.table.item(row, col)
        return item.text() if item else ""

    def set_router(self, router_name: str):
        """切换路由器时刷新所有相关选项"""
        self.router = get_router(router_name)
        self.router_name = router_name
        band_options = getattr(self.router, "BAND_LIST", ["2.4 GHz", "5 GHz"])
        if not hasattr(self.router, "BAND_LIST"):
            # TODO: 路由器需补充 BAND_LIST 字段
            pass

        band_col = self.headers.index("band")
        for r in range(self.table.rowCount()):
            band_widget = self.table.cellWidget(r, band_col)
            if isinstance(band_widget, ComboBox):
                band_widget.blockSignals(True)
                current = band_widget.currentText()
                band_widget.clear()
                band_widget.addItems(band_options)
                if current in band_options:
                    band_widget.setCurrentText(current)
                else:
                    band_widget.setCurrentIndex(0)
                band_widget.blockSignals(False)
                self._update_band_dependent(r, band_widget.currentText())

    def _update_band_dependent(self, row: int, band: str):
        mapping = {
            "wireless_mode": "WIRELESS",
            "channel": "CHANNEL",
            "bandwidth": "BANDWIDTH",
            "authentication_method": "AUTHENTICATION_METHOD",
        }
        for name, attr in mapping.items():
            col = self.headers.index(name)
            widget = self.table.cellWidget(row, col)
            if isinstance(widget, ComboBox):
                widget.blockSignals(True)
                widget.clear()
                if name == "authentication_method":
                    options = getattr(self.router, attr, [])
                    if not options:
                        # TODO: 若路由器区分频段的认证方式，请补充相关字段
                        pass
                else:
                    options = getattr(self.router, f"{attr}_2" if band == "2.4 GHz" else f"{attr}_5", [])
                    if not options:
                        # TODO: 补充路由器的 {attr}_2/{attr}_5 配置
                        pass
                widget.addItems(options)
                widget.blockSignals(False)

    def set_router_credentials(self, ssid: str, passwd: str) -> None:
        try:
            ssid_col = self.headers.index("ssid")
            passwd_col = self.headers.index("wpa_passwd")
        except ValueError:
            return
        for r in range(self.table.rowCount()):
            ssid_cell = self.table.cellWidget(r, ssid_col)
            if isinstance(ssid_cell, LineEdit):
                ssid_cell.setText(ssid)
            passwd_cell = self.table.cellWidget(r, passwd_col)
            if isinstance(passwd_cell, LineEdit):
                passwd_cell.setText(passwd)

    # ------------------------------------------------------------------
    # 保存
    def save_csv(self):
        data = []
        for r in range(self.table.rowCount()):
            row_data = {}
            for c, header in enumerate(self.headers):
                cell = self.table.cellWidget(r, c)
                if isinstance(cell, ComboBox):
                    text = cell.currentText()
                elif isinstance(cell, LineEdit):
                    text = cell.text()
                else:
                    item = self.table.item(r, c)
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

