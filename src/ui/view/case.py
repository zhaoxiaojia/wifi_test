"""Case (RvR Wi-Fi) configuration view and page.

This module contains both the *pure UI* widgets for the RvR Wi-Fi case
page (:class:`CaseView`) and the higher-level
(:class:`RvrWifiConfigPage`) widget that wires the view to the router /
CSV configuration logic.
"""

from __future__ import annotations

import logging
from contextlib import ExitStack, suppress
import csv
from pathlib import Path
from typing import Any

from PyQt5.QtCore import Qt, QSignalBlocker
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QVBoxLayout,
    QWidget,
    QTableWidgetItem,
)
from qfluentwidgets import CardWidget, ComboBox, LineEdit, PushButton, TableWidget, InfoBar, InfoBarPosition

from src.util.constants import AUTH_OPTIONS, OPEN_AUTH, Paths, RouterConst
from src.tools.router_tool.router_factory import get_router
from src.ui.view.theme import apply_theme, apply_font_and_selection
from src.ui.view.common import attach_view_to_page


class WifiTableWidget(TableWidget):
    """Wi-Fi parameter table widget (UI only, behaviour delegated to owner)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)


class CaseView(CardWidget):
    """Pure UI for the RvR Wi-Fi case page (form + table)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_theme(self)

        main_layout = QHBoxLayout(self)

        # Left-side form (single-row editor)
        form_box = QGroupBox(self)
        apply_theme(form_box, recursive=True)
        form_layout = QFormLayout(form_box)

        self.band_combo = ComboBox(form_box)
        form_layout.addRow("band", self.band_combo)

        self.wireless_combo = ComboBox(form_box)
        form_layout.addRow("wireless mode", self.wireless_combo)

        self.channel_combo = ComboBox(form_box)
        form_layout.addRow("channel", self.channel_combo)

        self.bandwidth_combo = ComboBox(form_box)
        form_layout.addRow("bandwidth", self.bandwidth_combo)

        self.auth_combo = ComboBox(form_box)
        self.auth_combo.addItems(AUTH_OPTIONS)
        form_layout.addRow("security", self.auth_combo)

        self.ssid_edit = LineEdit(form_box)
        form_layout.addRow("ssid", self.ssid_edit)

        self.passwd_edit = LineEdit(form_box)
        self.passwd_edit.setEchoMode(LineEdit.Password)
        form_layout.addRow("password", self.passwd_edit)

        test_widget = QWidget(form_box)
        test_layout = QHBoxLayout(test_widget)
        test_layout.setContentsMargins(0, 0, 0, 0)
        self.tx_check = QCheckBox("tx", test_widget)
        self.rx_check = QCheckBox("rx", test_widget)
        test_layout.addWidget(self.tx_check)
        test_layout.addWidget(self.rx_check)
        form_layout.addRow("direction", test_widget)

        btn_widget = QWidget(form_box)
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.del_btn = PushButton("Del", btn_widget)
        btn_layout.addWidget(self.del_btn)
        self.add_btn = PushButton("Add", btn_widget)
        btn_layout.addWidget(self.add_btn)
        form_layout.addRow(btn_widget)

        main_layout.addWidget(form_box, 2)

        # Right-side table
        self.table = WifiTableWidget(self)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setMinimumSectionSize(100)
        main_layout.addWidget(self.table, 5)

        apply_theme(header)
        apply_font_and_selection(
            self.table,
            family="Verdana",
            size_px=12,
            sel_text="#A6E3FF",
            sel_bg="#2B2B2B",
            grid="#3F3F46",
            header_bg="#0B0B0C",
            header_fg="#D0D0D0",
        )

        # Logical control map for the case (RVR Wi-Fi) page.
        # Keys follow: page_frame_group_purpose_type
        self.case_controls: dict[str, object] = {
            "case_main_wifi_band_combo": self.band_combo,
            "case_main_wifi_mode_combo": self.wireless_combo,
            "case_main_wifi_channel_combo": self.channel_combo,
            "case_main_wifi_bandwidth_combo": self.bandwidth_combo,
            "case_main_wifi_security_combo": self.auth_combo,
            "case_main_wifi_ssid_text": self.ssid_edit,
            "case_main_wifi_password_text": self.passwd_edit,
            "case_main_wifi_tx_check": self.tx_check,
            "case_main_wifi_rx_check": self.rx_check,
            "case_main_wifi_delete_btn": self.del_btn,
            "case_main_wifi_add_btn": self.add_btn,
            "case_main_wifi_table": self.table,
        }


class RvrWifiConfigPage(CardWidget):
    """RVR Wi-Fi test parameter configuration page (view + behaviour)."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("rvrWifiConfigPage")

        self.csv_path = self._compute_csv_path()
        self.router, self.router_name = self._load_router()
        self.headers, self.rows = self._load_csv()

        self._loading = False

        self.view = CaseView(self)
        attach_view_to_page(self, self.view, orientation=Qt.Horizontal)

        self.band_combo = self.view.band_combo
        self.wireless_combo = self.view.wireless_combo
        self.channel_combo = self.view.channel_combo
        self.bandwidth_combo = self.view.bandwidth_combo
        self.auth_combo = self.view.auth_combo
        self.ssid_edit = self.view.ssid_edit
        self.passwd_edit = self.view.passwd_edit
        self.tx_check = self.view.tx_check
        self.rx_check = self.view.rx_check
        self.del_btn = self.view.del_btn
        self.add_btn = self.view.add_btn
        self.table: WifiTableWidget = self.view.table  # type: ignore[assignment]

        band_list = getattr(self.router, "BAND_LIST", ["2.4G", "5G"])
        self.band_combo.addItems(band_list)

        self.band_combo.currentTextChanged.connect(self._on_band_changed)
        self.table.cellClicked.connect(self._on_table_cell_clicked)
        self.tx_check.stateChanged.connect(self._update_tx_rx)
        self.rx_check.stateChanged.connect(self._update_tx_rx)

        self.band_combo.currentTextChanged.connect(self._update_current_row)
        self.wireless_combo.currentTextChanged.connect(self._update_current_row)
        self.channel_combo.currentTextChanged.connect(self._update_current_row)
        self.bandwidth_combo.currentTextChanged.connect(self._update_current_row)
        self.auth_combo.currentTextChanged.connect(self._on_auth_changed)
        self.auth_combo.currentTextChanged.connect(self._update_current_row)
        self.passwd_edit.textChanged.connect(self._update_current_row)
        self.ssid_edit.textChanged.connect(self._update_current_row)

        if self.rows:
            self.refresh_table()
        else:
            self.reset_form()

    # --- router / CSV helpers -------------------------------------------------

    def _compute_csv_path(self, router_name: str | None = None) -> Path:
        csv_dir = Path(Paths.CONFIG_DIR) / "performance_test_csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        name = router_name or "rvr_wifi_setup"
        return (csv_dir / f"{name}.csv").resolve()

    def _load_router(self, name: str | None = None, address: str | None = None):
        from src.tools.config_loader import load_config

        try:
            cfg = load_config(refresh=True) or {}
            router_name = name or cfg.get("router", {}).get("name", "asusax86u")
            if address is None and cfg.get("router", {}).get("name") == router_name:
                address = cfg.get("router", {}).get("address")
            router = get_router(router_name, address)
        except Exception as e:
            logging.error("load router error: %s", e)
            router_name = name or "asusax86u"
            router = get_router(router_name, address)
        return (router, router_name)

    def _load_csv(self) -> tuple[list[str], list[dict[str, str]]]:
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
        headers: list[str] = default_headers
        rows: list[dict[str, str]] = []
        try:
            with open(self.csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    headers = [h.strip() for h in reader.fieldnames]
                for row in reader:
                    data = {h: (row.get(h) or "").strip() for h in headers}
                    rows.append(data)
        except FileNotFoundError:
            logging.warning("CSV not found: %s. Creating a new one with default headers.", self.csv_path)
            try:
                self.csv_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=default_headers)
                    writer.writeheader()
            except Exception as e:
                logging.error("Create CSV failed: %s", e)
        except Exception as e:
            InfoBar.error(title="Error", content=str(e), parent=self, position=InfoBarPosition.TOP)
            logging.exception("CSV load error: %s", e)
        logging.debug("Loaded headers %s with %d rows", headers, len(rows))
        return headers, rows

    def reload_csv(self) -> None:
        logging.info("Reloading CSV from %s", self.csv_path)
        self.headers, self.rows = self._load_csv()
        self.refresh_table()

    def reload_router(self) -> None:
        try:
            (self.router, self.router_name) = self._load_router()
            self.csv_path = self._compute_csv_path(self.router_name)
        except Exception as e:
            logging.error("reload router failed: %s", e)
            return
        self._update_band_options(self.band_combo.currentText())
        self._update_auth_options(self.wireless_combo.currentText())
        if not self.rows:
            self.reset_form()
        else:
            self._load_row_to_form(ensure_checked=True)

    def on_csv_file_changed(self, path: str) -> None:
        if not path:
            return
        logging.debug("CSV file changed: %s", path)
        self.csv_path = Path(path).resolve()
        logging.debug("Resolved CSV path: %s", self.csv_path)
        self.reload_csv()
        self._loading = True
        try:
            self._load_row_to_form(ensure_checked=True)
        finally:
            self._loading = False

    # --- form/table sync ------------------------------------------------------

    def _update_band_options(self, band: str) -> None:
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

    def _on_band_changed(self, band: str) -> None:
        self._update_band_options(band)
        self._update_current_row()

    def _update_auth_options(self, wireless: str) -> None:
        with QSignalBlocker(self.auth_combo):
            self.auth_combo.clear()
            self.auth_combo.addItems(AUTH_OPTIONS)
        if not self._loading:
            self._on_auth_changed(self.auth_combo.currentText())

    def _on_auth_changed(self, auth: str) -> None:
        if auth not in AUTH_OPTIONS:
            logging.warning("Unsupported auth method: %s", auth)
            return
        no_password = auth in OPEN_AUTH
        self.passwd_edit.setEnabled(not no_password)
        if no_password:
            self.passwd_edit.clear()

    def _update_current_row(self) -> None:
        if self._loading:
            return
        row_index = self.table.currentRow()
        if not (0 <= row_index < len(self.rows)):
            return
        row = self.rows[row_index]
        row["band"] = self.band_combo.currentText().strip()
        row["wireless_mode"] = self.wireless_combo.currentText().strip()
        row["channel"] = self.channel_combo.currentText().strip()
        row["bandwidth"] = self.bandwidth_combo.currentText().strip()
        row["security_mode"] = self.auth_combo.currentText().strip()
        row["password"] = self.passwd_edit.text()
        row["ssid"] = self.ssid_edit.text()
        for c, h in enumerate(self.headers):
            if h not in row:
                continue
            item = self.table.item(row_index, c + 1)
            if item is None:
                item = QTableWidgetItem()
                self.table.setItem(row_index, c + 1, item)
            item.setText(row[h])

    def refresh_table(self) -> None:
        self.table.clear()
        self.table.setRowCount(len(self.rows))
        self.table.setColumnCount(len(self.headers) + 1)
        self.table.setHorizontalHeaderLabels([" ", *self.headers])

        for r, row in enumerate(self.rows):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(checkbox.flags() | Qt.ItemIsUserCheckable)
            checkbox.setCheckState(
                Qt.Checked if row.get("tx", "0") == "1" or row.get("rx", "0") == "1" else Qt.Unchecked
            )
            self.table.setItem(r, 0, checkbox)
            for c, h in enumerate(self.headers):
                item = QTableWidgetItem(row.get(h, ""))
                self.table.setItem(r, c + 1, item)

        self.table.clearSelection()
        self._load_row_to_form(ensure_checked=True)

    def _update_tx_rx(self) -> None:
        if self._loading:
            return
        row_index = self.table.currentRow()
        if not (0 <= row_index < len(self.rows)):
            return
        row = self.rows[row_index]
        row["tx"] = "1" if self.tx_check.isChecked() else "0"
        row["rx"] = "1" if self.rx_check.isChecked() else "0"
        item = self.table.item(row_index, 0)
        if item is not None and item.flags() & Qt.ItemIsUserCheckable:
            checked = row.get("tx") == "1" or row.get("rx") == "1"
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def _sync_rows(self) -> None:
        self._collect_table_data()

    def _collect_table_data(self) -> None:
        data: list[dict[str, str]] = []
        for r in range(self.table.rowCount()):
            row: dict[str, str] = {}
            for c, h in enumerate(self.headers):
                item = self.table.item(r, c + 1)
                row[h] = item.text().strip() if item else ""
            data.append(row)
        self.rows = data

    def reset_form(self) -> None:
        self._loading = True
        try:
            if self.band_combo.count():
                self.band_combo.setCurrentIndex(0)
            self._update_band_options(self.band_combo.currentText())
            if self.wireless_combo.count():
                self.wireless_combo.setCurrentIndex(0)
            if self.channel_combo.count():
                self.channel_combo.setCurrentIndex(0)
            if self.bandwidth_combo.count():
                self.bandwidth_combo.setCurrentIndex(0)
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
        item = self.table.item(row, 0) if 0 <= row < self.table.rowCount() else None
        if item is None:
            self._load_row_to_form(ensure_checked=False)
            return
        clicked_checkbox = column == 0
        ensure_checked = not clicked_checkbox
        if clicked_checkbox and (item.flags() & Qt.ItemIsUserCheckable):
            item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)
        else:
            self._ensure_row_checked(row)
        self._load_row_to_form(ensure_checked=ensure_checked)

    def _ensure_row_checked(self, row: int) -> None:
        item = self.table.item(row, 0) if 0 <= row < self.table.rowCount() else None
        if item is not None and item.flags() & Qt.ItemIsUserCheckable:
            if item.checkState() != Qt.Checked:
                item.setCheckState(Qt.Checked)

    def _load_row_to_form(self, ensure_checked: bool = False) -> None:
        self._loading = True
        try:
            row_index = self.table.currentRow()
            if not (0 <= row_index < len(self.rows)):
                return
            data = self.rows[row_index]
            band = data.get("band", "")
            if ensure_checked:
                item = self.table.item(row_index, 0)
                if item is not None and item.flags() & Qt.ItemIsUserCheckable and item.checkState() != Qt.Checked:
                    item.setCheckState(Qt.Checked)

            with ExitStack() as stack:
                for w in (
                    self.band_combo,
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
                self.passwd_edit.setText(data.get("password", ""))
            with QSignalBlocker(self.ssid_edit):
                self.ssid_edit.setText(data.get("ssid", ""))
            with QSignalBlocker(self.tx_check):
                self.tx_check.setChecked(data.get("tx", "0") == "1")
            with QSignalBlocker(self.rx_check):
                self.rx_check.setChecked(data.get("rx", "0") == "1")
        finally:
            self._loading = False

    # --- public helpers -------------------------------------------------------

    def get_current_row_data(self) -> dict[str, str]:
        row_index = self.table.currentRow()
        if not (0 <= row_index < len(self.rows)):
            return {}
        return dict(self.rows[row_index])

    def get_current_wifi_params(self) -> tuple[str, str]:
        return (self.ssid_edit.text(), self.passwd_edit.text())

    def set_readonly(self, readonly: bool) -> None:
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
