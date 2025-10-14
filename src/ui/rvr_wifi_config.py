#!/usr/bin/env python
# encoding: utf-8
"""
RVR Wi-Fi configuration page
"""
from __future__ import annotations

import csv
from pathlib import Path

import logging
from contextlib import ExitStack
from PyQt5.QtCore import Qt, QSignalBlocker
from src.util.constants import AUTH_OPTIONS, OPEN_AUTH, Paths, RouterConst
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
from .theme import apply_theme, apply_font_and_selection

if TYPE_CHECKING:
    from .windows_case_config import CaseConfigPage

class WifiTableWidget(TableWidget):
    """支持拖拽排序并通知父页面同步行顺序的表格"""

    def __init__(self, page: "RvrWifiConfigPage"):
        super().__init__(page)
        self.page = page
        # 取消表格自身的选中状态，避免与勾选框操作冲突
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)

    def mousePressEvent(self, event):
        """点击空白区域时清除选择并重置表单"""
        super().mousePressEvent(event)
        if self.itemAt(event.pos()) is None:
            self.clearSelection()
            self.setCurrentItem(None)
            self.page.reset_form()


class RvrWifiConfigPage(CardWidget):
    """配置 RVR Wi-Fi 测试参数"""

    def __init__(self, case_config_page: "CaseConfigPage"):
        super().__init__()
        self.setObjectName("rvrWifiConfigPage")
        self.case_config_page = case_config_page
        combo = getattr(self.case_config_page, "router_name_combo", None)
        router_name = combo.currentText().lower() if combo is not None else ""
        self.csv_path = self._compute_csv_path(router_name)
        addr_edit = getattr(self.case_config_page, "router_addr_edit", None)
        addr = addr_edit.text() if addr_edit is not None else None
        self.router, self.router_name = self._load_router(router_name, addr)
        self.headers, self.rows = self._load_csv()
        # 标记是否处于数据加载阶段，用于屏蔽信号回调
        self._loading = False
        main_layout = QHBoxLayout(self)

        form_box = QGroupBox(self)
        apply_theme(form_box, recursive=True)
        form_layout = QFormLayout(form_box)
        self.band_combo = ComboBox(form_box)
        band_list = getattr(self.router, "BAND_LIST", ["2.4G", "5G"])
        self.band_combo.addItems(band_list)
        form_layout.addRow("band", self.band_combo)

        self.wireless_combo = ComboBox(form_box)
        form_layout.addRow("wireless_mode", self.wireless_combo)

        self.channel_combo = ComboBox(form_box)
        form_layout.addRow("channel", self.channel_combo)

        self.bandwidth_combo = ComboBox(form_box)
        form_layout.addRow("bandwidth", self.bandwidth_combo)

        self.auth_combo = ComboBox(form_box)
        self.auth_combo.addItems(AUTH_OPTIONS)
        self.auth_combo.setMinimumWidth(150)
        form_layout.addRow("security_mode", self.auth_combo)
        # 密码输入框，用于自动填充和测试流程引用
        self.ssid_edit = LineEdit(form_box)
        form_layout.addRow("ssid", self.ssid_edit)
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
        form_layout.addRow("direction", test_widget)

        btn_widget = QWidget(form_box)
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.del_btn = PushButton("Del", btn_widget)
        self.del_btn.clicked.connect(self.delete_row)
        btn_layout.addWidget(self.del_btn)
        self.add_btn = PushButton("Add", btn_widget)
        self.add_btn.clicked.connect(self.add_row)
        btn_layout.addWidget(self.add_btn)
        form_layout.addRow(btn_widget)

        main_layout.addWidget(form_box, 2)

        self.table = WifiTableWidget(self)

        # 禁用交替行颜色并避免样式表重新启用
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setStretchLastSection(True)
        # 无选中模式下使用 cellClicked 信号加载数据
        self.table.cellClicked.connect(self._on_table_cell_clicked)
        main_layout.addWidget(self.table, 5)

        apply_theme(header)
        apply_font_and_selection(
            self.table,
            family="Verdana", size_px=12,
            sel_text="#A6E3FF",  # 选中文字
            sel_bg="#2B2B2B",  # 选中背景
            header_bg="#202225",  # 表头/首行首列背景
            header_fg="#C9D1D9",  # 表头文字
            grid="#2E2E2E"  # 网格线/分隔线
        )

        self.band_combo.currentTextChanged.connect(self._on_band_changed)
        self.wireless_combo.currentTextChanged.connect(self._update_auth_options)
        self.wireless_combo.currentTextChanged.connect(self._update_current_row)
        self.channel_combo.currentTextChanged.connect(self._update_current_row)
        self.bandwidth_combo.currentTextChanged.connect(self._update_current_row)
        self.auth_combo.currentTextChanged.connect(self._on_auth_changed)
        self.auth_combo.currentTextChanged.connect(self._update_current_row)
        self.passwd_edit.textChanged.connect(self._update_current_row)
        self.ssid_edit.textChanged.connect(self._update_current_row)
        self._update_band_options(self.band_combo.currentText())
        self._update_auth_options(self.wireless_combo.currentText())
        self._on_auth_changed(self.auth_combo.currentText())
        self.refresh_table()

        # 监听主配置页面信号
        self.case_config_page.routerInfoChanged.connect(self.reload_router)
        self.case_config_page.csvFileChanged.connect(self.on_csv_file_changed)

    def _get_base_dir(self) -> Path:
        return Path(Paths.BASE_DIR)

    def _compute_csv_path(self, router_name: str) -> Path:
        csv_base = Path(Paths.CONFIG_DIR) / "performance_test_csv"
        return (csv_base / "rvr_wifi_setup.csv").resolve()

    def set_router_credentials(self, ssid: str, passwd: str) -> None:
        """设置路由器凭据并自动填充密码输入框"""
        self.ssid_edit.setText(ssid)
        self.passwd_edit.setText(passwd)

    def get_router_credentials(self) -> tuple[str, str]:
        """返回当前页面的路由器 SSID 和密码"""
        return self.ssid_edit.text(), self.passwd_edit.text()

    def set_readonly(self, readonly: bool) -> None:
        """切换页面只读状态"""
        widgets = (
            self.table,
            self.band_combo,
            self.wireless_combo,
            self.channel_combo,
            self.bandwidth_combo,
            self.auth_combo,
            self.ssid_edit,
            self.passwd_edit,
            self.tx_check,
            self.rx_check,
            self.add_btn,
            self.del_btn,
        )
        for w in widgets:
            w.setEnabled(not readonly)

    def _load_router(self, name: str | None = None, address: str | None = None):
        from src.tools.config_loader import load_config

        try:
            load_config.cache_clear()
            cfg = load_config(refresh=True) or {}
            router_name = name or cfg.get("router", {}).get("name", "asusax86u")
            if address is None and cfg.get("router", {}).get("name") == router_name:
                address = cfg.get("router", {}).get("address")
            router = get_router(router_name, address)
        except Exception as e:
            logging.error("load router error: %s", e)
            router_name = name or "asusax86u"
            router = get_router(router_name, address)
        return router, router_name

    def _load_csv(self):
        default_headers = [
            "band",
            "ssid",
            "wireless_mode",
            "channel",
            "bandwidth",
            "security_mode",
            "password",
            "tx",
            "rx",
        ]
        headers = default_headers
        rows: list[dict[str, str]] = []
        logging.debug("Loading CSV from %s", self.csv_path)
        if self.csv_path.exists():
            with open(self.csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or default_headers
                for row in reader:
                    rows.append({h: row.get(h, "") for h in headers})
        logging.debug("Loaded headers %s with %d rows", headers, len(rows))
        return headers, rows

    def reload_csv(self):
        """重新读取当前 CSV 并刷新表格"""
        logging.info("Reloading CSV from %s", self.csv_path)
        self.headers, self.rows = self._load_csv()
        self.refresh_table()

    def reload_router(self):
        """重新加载路由器配置并刷新频段相关选项"""
        combo = getattr(self.case_config_page, "router_name_combo", None)
        name = combo.currentText().lower() if combo is not None else self.router_name
        self.csv_path = self._compute_csv_path(name)
        try:
            addr_edit = getattr(self.case_config_page, "router_addr_edit", None)
            addr = addr_edit.text() if addr_edit is not None else None
            self.router = get_router(name, addr)
            self.router_name = name
        except Exception as e:
            logging.error("reload router error: %s", e)
            return
        band_list = getattr(self.router, "BAND_LIST", ["2.4G", "5G"])
        self.band_combo.blockSignals(True)
        self.band_combo.clear()
        self.band_combo.addItems(band_list)
        if band_list:
            self.band_combo.setCurrentText(band_list[0])
        self.band_combo.blockSignals(False)
        self.reload_csv()
        self._loading = True
        try:
            self._load_row_to_form(ensure_checked=True)
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
        # 确保使用绝对路径加载 CSV，避免目录切换引起的混淆
        logging.debug("CSV file changed: %s", path)
        self.csv_path = Path(path).resolve()
        logging.debug("Resolved CSV path: %s", self.csv_path)

        self.reload_csv()
        self._loading = True
        try:
            self._load_row_to_form(ensure_checked=True)
        finally:
            self._loading = False

    def _update_band_options(self, band: str):
        wireless = RouterConst.DEFAULT_WIRELESS_MODES[band]
        channel = {
            "2.4G": getattr(self.router, "CHANNEL_2", []),
            "5G": getattr(self.router, "CHANNEL_5", []),
        }[band]
        bandwidth = {
            "2.4G": getattr(self.router, "BANDWIDTH_2", []),
            "5G": getattr(self.router, "BANDWIDTH_5", []),
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
        """更新认证方式选项，固定为预设列表"""
        with QSignalBlocker(self.auth_combo):
            self.auth_combo.clear()
            self.auth_combo.addItems(AUTH_OPTIONS)
        if not self._loading:
            self._on_auth_changed(self.auth_combo.currentText())

    def _on_auth_changed(self, auth: str):
        """根据认证方式启用或禁用密码框"""
        if auth not in AUTH_OPTIONS:
            logging.warning("Unsupported auth method: %s", auth)
            return
        no_password = auth in OPEN_AUTH
        self.passwd_edit.setEnabled(not no_password)
        if no_password:
            self.passwd_edit.clear()

    def refresh_table(self):
        self.table.clear()
        self.table.setRowCount(len(self.rows))
        # 首列为勾选框，需额外预留一列
        self.table.setColumnCount(len(self.headers) + 1)
        self.table.setHorizontalHeaderLabels([" ", *self.headers])
        header = self.table.horizontalHeader()
        idx = self.headers.index("security_mode") + 1
        ssid = self.headers.index("ssid") + 1
        header.setSectionResizeMode(idx, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(ssid, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(idx, 150)
        self.table.setColumnWidth(ssid, 150)
        for r, row in enumerate(self.rows):
            # 勾选框列
            check_item = QTableWidgetItem()
            check_item.setFlags(
                Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )
            check_item.setCheckState(Qt.Unchecked)
            self.table.setItem(r, 0, check_item)
            for c, h in enumerate(self.headers):
                item = QTableWidgetItem(str(row.get(h, "")))
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.table.setItem(r, c + 1, item)
        self.table.clearSelection()
        self.table.setCurrentItem(None)
        self._load_row_to_form(ensure_checked=True)

    def _sync_rows(self):
        self._collect_table_data()

    def _collect_table_data(self):
        data: list[dict[str, str]] = []
        for r in range(self.table.rowCount()):
            row: dict[str, str] = {}
            for c, h in enumerate(self.headers):
                item = self.table.item(r, c + 1)
                row[h] = item.text() if item else ""
            data.append(row)
        self.rows = data

    def reset_form(self) -> None:
        """重置表单控件到默认状态"""
        self._loading = True
        try:
            with ExitStack() as stack:
                widgets = (
                    self.band_combo,
                    self.wireless_combo,
                    self.channel_combo,
                    self.bandwidth_combo,
                    self.auth_combo,
                    self.passwd_edit,
                    self.ssid_edit,
                    self.tx_check,
                    self.rx_check,
                )
                for w in widgets:
                    stack.enter_context(QSignalBlocker(w))
                if self.rows:
                    data = self.rows[-1]
                    band = data.get("band", "")
                    self.band_combo.setCurrentText(band)
                    self._update_band_options(band)
                    self.wireless_combo.setCurrentText(data.get("wireless_mode", ""))
                    self.channel_combo.setCurrentText(data.get("channel", ""))
                    self.bandwidth_combo.setCurrentText(data.get("bandwidth", ""))
                    self._update_auth_options(self.wireless_combo.currentText())
                    self.auth_combo.setCurrentText(data.get("security_mode", ""))
                    self._on_auth_changed(self.auth_combo.currentText())
                    self.passwd_edit.setText(data.get("password", ""))
                    self.ssid_edit.setText(data.get("ssid", ""))
                    self.tx_check.setChecked(data.get("tx", "0") == "1")
                    self.rx_check.setChecked(data.get("rx", "0") == "1")
                else:
                    if self.band_combo.count():
                        self.band_combo.setCurrentIndex(0)
                    self._update_band_options(self.band_combo.currentText())

                    if self.wireless_combo.count():
                        self.wireless_combo.setCurrentIndex(0)
                    if self.channel_combo.count():
                        self.channel_combo.setCurrentIndex(0)
                    if self.bandwidth_combo.count():
                        self.bandwidth_combo.setCurrentIndex(0)
                    self._update_auth_options(self.wireless_combo.currentText())

                    if self.auth_combo.count():
                        self.auth_combo.setCurrentIndex(0)
                    self._on_auth_changed(self.auth_combo.currentText())

                    self.passwd_edit.clear()
                    self.ssid_edit.clear()
                    self.tx_check.setChecked(False)
                    self.rx_check.setChecked(False)
        finally:
            self._loading = False

    def _on_table_cell_clicked(self, row: int, column: int) -> None:
        """When a row cell is clicked, sync form and checkbox state appropriately."""
        item = self.table.item(row, 0) if 0 <= row < self.table.rowCount() else None
        if item is None:
            self._load_row_to_form(ensure_checked=False)
            return
        clicked_checkbox = column == 0
        should_uncheck = item.checkState() == Qt.Checked and (clicked_checkbox or column != 0)
        if should_uncheck:
            item.setCheckState(Qt.Unchecked)
            self._load_row_to_form(ensure_checked=False)
            return
        ensure_checked = column != 0
        if ensure_checked:
            self._ensure_row_checked(row)
        self._load_row_to_form(ensure_checked=ensure_checked)

    def _ensure_row_checked(self, row: int) -> None:
        item = self.table.item(row, 0) if 0 <= row < self.table.rowCount() else None
        if item is not None and item.flags() & Qt.ItemIsUserCheckable:
            if item.checkState() != Qt.Checked:
                item.setCheckState(Qt.Checked)

    def _load_row_to_form(self, ensure_checked: bool = False):
        self._loading = True
        try:
            row_index = self.table.currentRow()
            if not (0 <= row_index < len(self.rows)):
                self.reset_form()
                return
            data = self.rows[row_index]
            if ensure_checked:
                self._ensure_row_checked(row_index)

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
                        self.ssid_edit,
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
                self.auth_combo.setCurrentText(data.get("security_mode", ""))
            with QSignalBlocker(self.passwd_edit):
                self._on_auth_changed(self.auth_combo.currentText())
            with QSignalBlocker(self.passwd_edit):
                self.passwd_edit.setText(data.get("password", ""))
            with QSignalBlocker(self.ssid_edit):
                self.ssid_edit.setText(data.get("ssid", ""))
            with QSignalBlocker(self.tx_check):
                self.tx_check.setChecked(data.get("tx", "0") == "1")
            with QSignalBlocker(self.rx_check):
                self.rx_check.setChecked(data.get("rx", "0") == "1")
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
            col = self.headers.index(col_name) + 1
        except ValueError:
            return
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem(value)
            item.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(row, col, item)
        else:
            item.setText(value)
        self.save_csv()

    def _update_current_row(self, *args):
        if self._loading:
            return
        row = self.table.currentRow()
        if not (0 <= row < len(self.rows)):
            return
        band = self.band_combo.currentText()
        data = {
            "band": band,
            "wireless_mode": self.wireless_combo.currentText(),
            "channel": self.channel_combo.currentText(),
            "bandwidth": self.bandwidth_combo.currentText(),
            "security_mode": self.auth_combo.currentText(),
            "ssid": self.ssid_edit.text(),
            "password": self.passwd_edit.text(),
        }
        self.rows[row].update(data)
        for key, value in data.items():
            try:
                col = self.headers.index(key) + 1
            except ValueError:
                continue
            item = self.table.item(row, col)
            if item is None:
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.table.setItem(row, col, item)
            else:
                item.setText(value)
        self.save_csv()

    def add_row(self):
        band = self.band_combo.currentText()
        if not self.ssid_edit.text():
            InfoBar.error(title="Error", content="Pls input ssid", parent=self, position=InfoBarPosition.TOP)
            return
        if self.passwd_edit.isEnabled() and not self.passwd_edit.text():
            InfoBar.error(title="Error", content="Pls input password", parent=self, position=InfoBarPosition.TOP)
            return
        ssid = self.ssid_edit.text()
        row = {
            "band": band,
            "wireless_mode": self.wireless_combo.currentText(),
            "channel": self.channel_combo.currentText(),
            "bandwidth": self.bandwidth_combo.currentText(),
            "security_mode": self.auth_combo.currentText(),
            "ssid": ssid,
            "password": self.passwd_edit.text(),
            "tx": "1" if self.tx_check.isChecked() else "0",
            "rx": "1" if self.rx_check.isChecked() else "0",
        }
        self.rows.append(row)
        self.refresh_table()
        self.save_csv()

    def delete_row(self):
        new_rows: list[dict[str, str]] = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.checkState() == Qt.Checked:
                continue
            row_data: dict[str, str] = {}
            for c, h in enumerate(self.headers):
                cell = self.table.item(r, c + 1)
                row_data[h] = cell.text() if cell else ""
            new_rows.append(row_data)
        self.rows = new_rows
        self.refresh_table()
        self.save_csv()

    def save_csv(self):
        if self.passwd_edit.isEnabled() and not self.passwd_edit.text():
            InfoBar.error(title="Error", content="Pls input password", parent=self, position=InfoBarPosition.TOP)
            return
        self._collect_table_data()
        if any(not row.get("ssid") for row in self.rows):
            InfoBar.error(title="Error", content="Pls input ssid", parent=self, position=InfoBarPosition.TOP)
            return
        try:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(self.rows)
            logging.info("CSV saved to %s", self.csv_path)
        except Exception as e:
            InfoBar.error(title="Error", content=str(e), parent=self, position=InfoBarPosition.TOP)
