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
from contextlib import ExitStack
from PyQt5.QtCore import Qt, QSignalBlocker
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
        self._loading = False
        base = Path.cwd()
        if hasattr(sys, "_MEIPASS"):
            base = Path(sys._MEIPASS)
            if not (base / "config").exists():
                base = Path.cwd()
        self.config_path = (base / "config" / "config.yaml").resolve()
        router_name = ""
        combo = getattr(self.case_config_page, "router_name_combo", None)
        if combo is not None:
            router_name = combo.currentText().lower()
        csv_base = base / "config" / "performance_test_csv"
        if "asus" in router_name:
            csv_base = csv_base / "asus"
        elif "xiaomi" in router_name:
            csv_base = csv_base / "xiaomi"
        else:
            csv_base = base / "config"
        self.csv_path = (csv_base / "rvr_wifi_setup.csv").resolve()
        print(f"reload_router: selected router={name}, csv_path={self.csv_path}")
        print(f"reload_router: rows before reload_csv {self.rows}")
        self.router, self.router_name = self._load_router()
        self.headers, self.rows = self._load_csv()
        # 当前页面使用的路由器 SSID
        self.ssid: str = ""
        # 标记是否处于数据加载阶段，用于屏蔽信号回调
        self._loading = False
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
        self.auth_combo.setMinimumWidth(150)
        form_layout.addRow("authentication", self.auth_combo)
        # 密码输入框，用于自动填充和测试流程引用
        self.passwd_edit = LineEdit(form_box)
        form_layout.addRow("password", self.passwd_edit)
        self.auth_combo.currentTextChanged.connect(self._on_auth_changed)

        test_widget = QWidget(form_box)
        test_layout = QHBoxLayout(test_widget)
        test_layout.setContentsMargins(0, 0, 0, 0)
        self.tx_check = QCheckBox("tx", test_widget)
        self.rx_check = QCheckBox("rx", test_widget)
        test_layout.addWidget(self.tx_check)
        test_layout.addWidget(self.rx_check)
        self.tx_check.stateChanged.connect(self._update_tx_rx)
        self.rx_check.stateChanged.connect(self._update_tx_rx)
        form_layout.addRow("test_type", test_widget)

        self.data_row_edit = LineEdit(form_box)
        form_layout.addRow("data_row", self.data_row_edit)

        btn_widget = QWidget(form_box)
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.add_btn = PushButton("Add", btn_widget)
        self.add_btn.clicked.connect(self.add_row)
        btn_layout.addWidget(self.add_btn)
        self.del_btn = PushButton("Del", btn_widget)
        self.del_btn.clicked.connect(self.delete_row)
        btn_layout.addWidget(self.del_btn)
        self.save_btn = PushButton("Save", btn_widget)
        self.save_btn.clicked.connect(self.save_csv)
        btn_layout.addWidget(self.save_btn)
        form_layout.addRow(btn_widget)

        main_layout.addWidget(form_box, 1)

        self.table = WifiTableWidget(self)
        # 禁用交替行颜色并避免样式表重新启用
        self.table.setAlternatingRowColors(False)
        self.table.setStyleSheet(
            self.table.styleSheet()
            + "QTableView {alternate-background-color: transparent;}"
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._load_row_to_form)
        main_layout.addWidget(self.table, 2)

        self.band_combo.currentTextChanged.connect(self._on_band_changed)
        self.wireless_combo.currentTextChanged.connect(self._update_auth_options)
        self.wireless_combo.currentTextChanged.connect(self._update_current_row)
        self.channel_combo.currentTextChanged.connect(self._update_current_row)
        self.bandwidth_combo.currentTextChanged.connect(self._update_current_row)
        self.auth_combo.currentTextChanged.connect(self._on_auth_changed)
        self.auth_combo.currentTextChanged.connect(self._update_current_row)
        self.passwd_edit.textChanged.connect(self._update_current_row)
        self.data_row_edit.textChanged.connect(self._update_current_row)
        self._update_band_options(self.band_combo.currentText())
        self._update_auth_options(self.wireless_combo.currentText())
        self._on_auth_changed(self.auth_combo.currentText())
        self.refresh_table()

        # 监听主配置页面信号
        self.case_config_page.routerInfoChanged.connect(self.reload_router)
        self.case_config_page.csvFileChanged.connect(self.on_csv_file_changed)

    def set_router_credentials(self, ssid: str, passwd: str) -> None:
        """设置路由器凭据并自动填充密码输入框"""
        self.ssid = ssid
        self.passwd_edit.setText(passwd)

    def get_router_credentials(self) -> tuple[str, str]:
        """返回当前页面的路由器 SSID 和密码"""
        return self.ssid, self.passwd_edit.text()

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
        default_headers = [
            "band",
            "wireless_mode",
            "channel",
            "bandwidth",
            "authentication",
            "ssid",
            "password",
            "tx",
            "rx",
            "data_row",
        ]
        headers = default_headers
        rows: list[dict[str, str]] = []
        if self.csv_path.exists():
            with open(self.csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or default_headers
                for row in reader:
                    rows.append({h: row.get(h, "") for h in headers})
        print(f"_load_csv: router={self.router_name}, csv_path={self.csv_path}")
        print(f"_load_csv: headers={headers}, rows_count={len(rows)}")
        return headers, rows

    def reload_csv(self):
        """重新读取当前 CSV 并刷新表格"""
        print(f"reload_csv: router={self.router_name}, csv_path={self.csv_path}")
        self.headers, self.rows = self._load_csv()
        print(f"reload_csv: headers={self.headers}, rows_count={len(self.rows)}")
        print(f"reload_csv: before refresh_table rows={self.rows}")
        self.refresh_table()
        print(f"reload_csv: after refresh_table rows={self.rows}")

    def reload_router(self):
        """重新加载路由器配置并刷新频段相关选项"""
        name = ""
        combo = getattr(self.case_config_page, "router_name_combo", None)
        if combo is not None:
            name = combo.currentText().lower()
        else:
            cfg = getattr(self.case_config_page, "config", {})
            if isinstance(cfg, dict):
                name = cfg.get("router", {}).get("name", self.router_name).lower()
        # 根据路由器名称重新计算 CSV 路径
        base = Path.cwd()
        if hasattr(sys, "_MEIPASS"):
            base = Path(sys._MEIPASS)
            if not (base / "config").exists():
                base = Path.cwd()
        csv_base = base / "config" / "performance_test_csv"
        if "asus" in name:
            csv_base = csv_base / "asus"
        elif "xiaomi" in name:
            csv_base = csv_base / "xiaomi"
        else:
            csv_base = base / "config"
        self.csv_path = (csv_base / "rvr_wifi_setup.csv").resolve()

        try:
            self.router = get_router(name)
            self.router_name = name
        except Exception as e:
            print(f"reload router error: {e}")
            return
        base = self.config_path.parent.parent
        csv_base = base / "config" / "performance_test_csv"
        router_name = name.lower()
        if "asus" in router_name:
            csv_base = csv_base / "asus"
        elif "xiaomi" in router_name:
            csv_base = csv_base / "xiaomi"
        else:
            csv_base = base / "config"
        self.csv_path = (csv_base / "rvr_wifi_setup.csv").resolve()
        print(f"reload_router: selected router={name}, csv_path={self.csv_path}")
        print(f"reload_router: rows before reload_csv {self.rows}")
        band_list = getattr(self.router, "BAND_LIST", ["2.4 GHz", "5 GHz"])
        self.band_combo.blockSignals(True)
        self.band_combo.clear()
        self.band_combo.addItems(band_list)
        current_band = band_list[0] if band_list else ""
        if current_band:
            self.band_combo.setCurrentText(current_band)
        self.band_combo.blockSignals(False)
        self.reload_csv()
        print(f"reload_router: headers={self.headers}, rows_count={len(self.rows)}")
        print(f"reload_router: rows after reload_csv {self.rows}")
        self._loading = True
        try:
            self._load_row_to_form()
        finally:
            self._loading = False
        if not self.rows:
            with ExitStack() as stack:
                for w in (self.wireless_combo, self.channel_combo, self.bandwidth_combo, self.auth_combo):
                    stack.enter_context(QSignalBlocker(w))
                self._update_band_options(self.band_combo.currentText())
            with ExitStack() as stack:
                stack.enter_context(QSignalBlocker(self.auth_combo))
                stack.enter_context(QSignalBlocker(self.passwd_edit))
                self._update_auth_options(self.wireless_combo.currentText())
            self._on_auth_changed(self.auth_combo.currentText())

    def on_csv_file_changed(self, path: str) -> None:
        """响应 CSV 文件变更"""
        if not path:
            return
        self.csv_path = Path(path)
        print(f"on_csv_file_changed: router={self.router_name}, csv_path={self.csv_path}")
        print(f"on_csv_file_changed: rows before reload_csv {self.rows}")
        self.reload_csv()
        print(f"on_csv_file_changed: headers={self.headers}, rows_count={len(self.rows)}")
        print(f"on_csv_file_changed: rows after reload_csv {self.rows}")
        self._loading = True
        try:
            self._load_row_to_form()
        finally:
            self._loading = False

    def _update_band_options(self, band: str):
        print(f'_update_band_options {self.router}')
        wireless = {
            "2.4 GHz": getattr(self.router, "WIRELESS_2", []),
            "5 GHz": getattr(self.router, "WIRELESS_5", []),
        }[band]
        channel = {
            "2.4 GHz": getattr(self.router, "CHANNEL_2", []),
            "5 GHz": getattr(self.router, "CHANNEL_5", []),
        }[band]
        bandwidth = {
            "2.4 GHz": getattr(self.router, "BANDWIDTH_2", []),
            "5 GHz": getattr(self.router, "BANDWIDTH_5", []),
        }[band]
        with QSignalBlocker(self.wireless_combo), QSignalBlocker(self.channel_combo), QSignalBlocker(
            self.bandwidth_combo
        ):
            self.wireless_combo.clear()
            self.wireless_combo.addItems(wireless)
            self.channel_combo.clear()
            self.channel_combo.addItems(channel)
            self.bandwidth_combo.clear()
            self.bandwidth_combo.addItems(bandwidth)
        if not self._loading:
            self._update_auth_options(self.wireless_combo.currentText())

    def _on_band_changed(self, band: str):
        self._update_band_options(band)
        self._update_current_row()

    def _update_auth_options(self, wireless: str):
        with QSignalBlocker(self.auth_combo):
            self.auth_combo.clear()
            if "Legacy" in wireless:
                self.auth_combo.addItems(
                    getattr(self.router, "AUTHENTICATION_METHOD_LEGCY", [])
                )
            else:
                self.auth_combo.addItems(
                    getattr(self.router, "AUTHENTICATION_METHOD", [])
                )
        if not self._loading:
            self._on_auth_changed(self.auth_combo.currentText())

    def _on_auth_changed(self, auth: str):
        # 调整密码框逻辑
        need_password = auth not in ("Open System", "无加密(允许所有人连接)")
        self.passwd_edit.setEnabled(need_password)
        if not need_password:
            self.passwd_edit.clear()

    def refresh_table(self):
        current = self.table.currentRow()
        self.table.clear()
        self.table.setRowCount(len(self.rows))
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        header = self.table.horizontalHeader()
        idx = self.headers.index("authentication")
        ssid = self.headers.index("ssid")
        header.setSectionResizeMode(idx, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(ssid, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(idx, 150)
        self.table.setColumnWidth(ssid, 150)
        for r, row in enumerate(self.rows):
            for c, h in enumerate(self.headers):
                item = QTableWidgetItem(str(row.get(h, "")))
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.table.setItem(r, c, item)
        if 0 <= current < self.table.rowCount():
            self.table.selectRow(current)
        elif self.table.rowCount():
            self.table.selectRow(0)
        else:
            self._load_row_to_form()

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

    def _load_row_to_form(self):
        self._loading = True
        try:
            row_index = self.table.currentRow()
            if not (0 <= row_index < len(self.rows)):
                return
            data = self.rows[row_index]

            band = data.get("band", "")
            with QSignalBlocker(self.band_combo):
                self.band_combo.setCurrentText(band)
            with ExitStack() as stack:
                for w in (
                        self.wireless_combo,
                        self.channel_combo,
                        self.bandwidth_combo,
                        self.auth_combo,
                        self.passwd_edit,
                ):
                    stack.enter_context(QSignalBlocker(w))
                self._update_band_options(band)

            with QSignalBlocker(self.wireless_combo):
                self.wireless_combo.setCurrentText(data.get("wireless_mode", ""))
            with ExitStack() as stack:
                stack.enter_context(QSignalBlocker(self.auth_combo))
                stack.enter_context(QSignalBlocker(self.passwd_edit))
                self._update_auth_options(self.wireless_combo.currentText())
                self._on_auth_changed(self.auth_combo.currentText())
            with QSignalBlocker(self.channel_combo):
                self.channel_combo.setCurrentText(data.get("channel", ""))
            with QSignalBlocker(self.bandwidth_combo):
                self.bandwidth_combo.setCurrentText(data.get("bandwidth", ""))
            with QSignalBlocker(self.auth_combo):
                self.auth_combo.setCurrentText(data.get("authentication", ""))
            with QSignalBlocker(self.passwd_edit):
                self._on_auth_changed(self.auth_combo.currentText())
            with QSignalBlocker(self.passwd_edit):
                self.passwd_edit.setText(data.get("password", ""))
            with QSignalBlocker(self.tx_check):
                self.tx_check.setChecked(data.get("tx", "0") == "1")
            with QSignalBlocker(self.rx_check):
                self.rx_check.setChecked(data.get("rx", "0") == "1")
            with QSignalBlocker(self.data_row_edit):
                self.data_row_edit.setText(data.get("data_row", ""))
        finally:
            self._loading = False

    def _update_tx_rx(self, state: int):
        row = self.table.currentRow()
        if not (0 <= row < len(self.rows)):
            return
        sender = self.sender()
        if sender not in (self.tx_check, self.rx_check):
            return
        col_name = "tx" if sender is self.tx_check else "rx"
        value = "1" if state == Qt.Checked else "0"
        self.rows[row][col_name] = value
        try:
            col = self.headers.index(col_name)
        except ValueError:
            return
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem(value)
            item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(row, col, item)
        else:
            item.setText(value)

    def _update_current_row(self, *args):
        if self._loading:
            return
        row = self.table.currentRow()
        if not (0 <= row < len(self.rows)):
            return
        band = self.band_combo.currentText()
        # if band == "2.4 GHz":
        #     ssid = self.case_config_page.ssid_2g_edit.text()
        # else:
        #     ssid = self.case_config_page.ssid_5g_edit.text()
        data = {
            "band": band,
            "wireless_mode": self.wireless_combo.currentText(),
            "channel": self.channel_combo.currentText(),
            "bandwidth": self.bandwidth_combo.currentText(),
            "authentication": self.auth_combo.currentText(),
            # "ssid": ssid,
            "password": self.passwd_edit.text(),
            "data_row": self.data_row_edit.text(),
        }
        self.rows[row].update(data)
        for key, value in data.items():
            try:
                col = self.headers.index(key)
            except ValueError:
                continue
            item = self.table.item(row, col)
            if item is None:
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.table.setItem(row, col, item)
            else:
                item.setText(value)

    def add_row(self):
        band = self.band_combo.currentText()
        auth = self.auth_combo.currentText()
        if auth not in ("Open System", "无加密（允许所有人连接）") and not self.passwd_edit.text():
            InfoBar.error(title="Error", content="Pls input password", parent=self, position=InfoBarPosition.TOP)
            return
        if band == "2.4 GHz":
            ssid = self.case_config_page.ssid_2g_edit.text()
        else:
            ssid = self.case_config_page.ssid_5g_edit.text()
        row = {
            "band": band,
            "wireless_mode": self.wireless_combo.currentText(),
            "channel": self.channel_combo.currentText(),
            "bandwidth": self.bandwidth_combo.currentText(),
            "authentication": self.auth_combo.currentText(),
            "ssid": ssid,
            "password": self.passwd_edit.text(),
            "tx": "1" if self.tx_check.isChecked() else "0",
            "rx": "1" if self.rx_check.isChecked() else "0",
            "data_row": self.data_row_edit.text(),
        }
        self.rows.append(row)
        self.refresh_table()
        if self.rows:
            self.table.selectRow(len(self.rows) - 1)

    def delete_row(self):
        self._collect_table_data()
        row = self.table.currentRow()
        if 0 <= row < len(self.rows):
            self.rows.pop(row)
            self.refresh_table()

    def save_csv(self):
        band = self.band_combo.currentText()
        auth = self.auth_combo.currentText()
        if auth not in ("Open System", "无加密（允许所有人连接）") and not self.passwd_edit.text():
            InfoBar.error(title="Error", content="Pls input password", parent=self, position=InfoBarPosition.TOP)
            return
        self._collect_table_data()
        try:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(self.rows)
            InfoBar.success(title="Hint", content="Saved", parent=self, position=InfoBarPosition.TOP)
        except Exception as e:
            InfoBar.error(title="Error", content=str(e), parent=self, position=InfoBarPosition.TOP)
