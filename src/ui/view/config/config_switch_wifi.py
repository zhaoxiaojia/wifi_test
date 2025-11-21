"""Switch Wi-Fi specific widgets and helpers for the Config page."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from PyQt5.QtCore import Qt, QSignalBlocker
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)
from qfluentwidgets import ComboBox, LineEdit, PushButton, InfoBar, InfoBarPosition

from src.util.constants import (
    AUTH_OPTIONS,
    SWITCH_WIFI_ENTRY_PASSWORD_FIELD,
    SWITCH_WIFI_ENTRY_SECURITY_FIELD,
    SWITCH_WIFI_ENTRY_SSID_FIELD,
)
from src.ui.view.theme import (
    SWITCH_WIFI_TABLE_HEADER_BG,
    SWITCH_WIFI_TABLE_HEADER_FG,
    SWITCH_WIFI_TABLE_SELECTION_BG,
    SWITCH_WIFI_TABLE_SELECTION_FG,
    apply_font_and_selection,
)


def normalize_switch_wifi_manual_entries(entries: Any) -> list[dict[str, str]]:
    """Normalise manual Wi-Fi entries for switch Wi-Fi stability tests."""
    normalized: list[dict[str, str]] = []
    if isinstance(entries, Sequence) and not isinstance(entries, (str, bytes)):
        for item in entries:
            if not isinstance(item, Mapping):
                continue
            ssid = (
                str(item.get(SWITCH_WIFI_ENTRY_SSID_FIELD, "") or "")
                .strip()
            )
            mode = (
                str(
                    item.get(
                        SWITCH_WIFI_ENTRY_SECURITY_FIELD,
                        AUTH_OPTIONS[0],
                    )
                    or AUTH_OPTIONS[0]
                )
                .strip()
            )
            if mode not in AUTH_OPTIONS:
                mode = AUTH_OPTIONS[0]
            password = str(
                item.get(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, "") or ""
            )
            normalized.append(
                {
                    SWITCH_WIFI_ENTRY_SSID_FIELD: ssid,
                    SWITCH_WIFI_ENTRY_SECURITY_FIELD: mode,
                    SWITCH_WIFI_ENTRY_PASSWORD_FIELD: password,
                }
            )
    return normalized


class SwitchWifiManualEditor(QWidget):
    """
    Editor widget for maintaining a list of Wi‑Fi network credentials that can
    be switched manually.

    Presents a table of SSID, security mode and password entries and form
    controls to add or remove rows. Emits an ``entriesChanged`` signal when
    the underlying list of dictionaries representing the entries is updated.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[dict[str, str]] = []
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["SSID", "Security Mode", "Password"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        apply_font_and_selection(
            self.table,
            header_bg=SWITCH_WIFI_TABLE_HEADER_BG,
            header_fg=SWITCH_WIFI_TABLE_HEADER_FG,
            sel_bg=SWITCH_WIFI_TABLE_SELECTION_BG,
            sel_text=SWITCH_WIFI_TABLE_SELECTION_FG,
        )
        layout.addWidget(self.table)

        # Input rows: keep controls simple inside the editor itself.
        # labels in a separate column.
        inputs_column = QVBoxLayout()
        inputs_column.setContentsMargins(0, 0, 0, 0)
        inputs_column.setSpacing(4)

        self.ssid_edit = LineEdit(self)
        self.ssid_edit.setPlaceholderText("SSID")
        inputs_column.addWidget(self.ssid_edit)

        self.security_combo = ComboBox(self)
        self.security_combo.addItems(AUTH_OPTIONS)
        self.security_combo.setMinimumWidth(160)
        inputs_column.addWidget(self.security_combo)

        self.password_edit = LineEdit(self)
        self.password_edit.setPlaceholderText("Password (optional)")
        inputs_column.addWidget(self.password_edit)

        layout.addLayout(inputs_column)

        buttons_row = QHBoxLayout()
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(8)

        self.add_btn = PushButton("Add", self)
        self.del_btn = PushButton("Remove", self)
        buttons_row.addWidget(self.add_btn)
        buttons_row.addWidget(self.del_btn)
        buttons_row.addStretch(1)
        layout.addLayout(buttons_row)

        self.table.currentCellChanged.connect(self._on_current_row_changed)
        self.add_btn.clicked.connect(self._on_add_entry)
        self.del_btn.clicked.connect(self._on_delete_entry)
        self.ssid_edit.textChanged.connect(
            lambda text: self._update_current_entry(SWITCH_WIFI_ENTRY_SSID_FIELD, text)
        )
        self.security_combo.currentTextChanged.connect(
            lambda text: self._update_current_entry(SWITCH_WIFI_ENTRY_SECURITY_FIELD, text)
        )
        self.password_edit.textChanged.connect(
            lambda text: self._update_current_entry(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, text)
        )

        self._refresh_table()

    # Public API ---------------------------------------------------------

    def set_entries(self, entries: Sequence[Mapping[str, Any]] | None) -> None:
        """Replace the underlying entry list and refresh the UI."""
        self._entries = [
            {
                SWITCH_WIFI_ENTRY_SSID_FIELD: str(e.get(SWITCH_WIFI_ENTRY_SSID_FIELD, "") or ""),
                SWITCH_WIFI_ENTRY_SECURITY_FIELD: str(
                    e.get(SWITCH_WIFI_ENTRY_SECURITY_FIELD, "") or ""
                ),
                SWITCH_WIFI_ENTRY_PASSWORD_FIELD: str(
                    e.get(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, "") or ""
                ),
            }
            for e in (entries or [])
        ]
        with QSignalBlocker(self.table):
            self._refresh_table()

    def entries(self) -> list[dict[str, str]]:
        """Return a deep copy of current entries."""
        return [dict(e) for e in self._entries]

    def serialize(self) -> list[dict[str, str]]:
        """Return entries in a config-friendly format (SSID/security/password)."""
        return self.entries()

    def set_manual_editing_enabled(self, enabled: bool) -> None:
        """Enable/disable manual editing controls while keeping table visible."""
        for w in (
            self.ssid_edit,
            self.security_combo,
            self.password_edit,
            self.add_btn,
            self.del_btn,
        ):
            w.setEnabled(bool(enabled))

    def serialize(self) -> list[dict[str, str]]:
        """Return entries in a config-friendly format (SSID/security/password)."""
        return self.entries()

    # Internal helpers ---------------------------------------------------

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            for col, key in enumerate(
                [
                    SWITCH_WIFI_ENTRY_SSID_FIELD,
                    SWITCH_WIFI_ENTRY_SECURITY_FIELD,
                    SWITCH_WIFI_ENTRY_PASSWORD_FIELD,
                ]
            ):
                value = entry.get(key, "")
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, col, item)
        if self._entries:
            self.table.selectRow(0)
        else:
            self._clear_form()

    def _clear_form(self) -> None:
        with QSignalBlocker(self.ssid_edit):
            self.ssid_edit.clear()
        with QSignalBlocker(self.security_combo):
            self.security_combo.setCurrentIndex(0)
        with QSignalBlocker(self.password_edit):
            self.password_edit.clear()

    def _on_current_row_changed(self, current_row: int, _current_col: int, *_args) -> None:
        if self._loading:
            return
        if 0 <= current_row < len(self._entries):
            entry = self._entries[current_row]
            with QSignalBlocker(self.ssid_edit):
                self.ssid_edit.setText(entry.get(SWITCH_WIFI_ENTRY_SSID_FIELD, ""))
            with QSignalBlocker(self.password_edit):
                self.password_edit.setText(entry.get(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, ""))
            with QSignalBlocker(self.security_combo):
                security = self._entries[current_row].get(SWITCH_WIFI_ENTRY_SECURITY_FIELD, "")
                index = self.security_combo.findText(security)
                if index < 0:
                    index = 0
                self.security_combo.setCurrentIndex(index)
        else:
            self._clear_form()

    def _on_add_entry(self) -> None:
        ssid = self.ssid_edit.text().strip()
        security = self.security_combo.currentText().strip()
        password = self.password_edit.text()
        if not ssid:
            return
        # OPEN System 无需密码；其他安全模式必须提供密码。
        if security != "Open System" and not password:
            parent_widget = self.window() if isinstance(self.window(), QWidget) else self
            InfoBar.error(
                title="Wi-Fi list",
                content="Password is required for the selected Security mode.",
                parent=parent_widget,
                position=InfoBarPosition.TOP,
            )
            return
        entry = {
            SWITCH_WIFI_ENTRY_SSID_FIELD: ssid,
            SWITCH_WIFI_ENTRY_SECURITY_FIELD: security,
            SWITCH_WIFI_ENTRY_PASSWORD_FIELD: password,
        }
        self._entries.append(entry)
        self._refresh_table()

    def _on_delete_entry(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self._entries):
            del self._entries[row]
            self._refresh_table()

    def _update_current_entry(self, field: str, value: str) -> None:
        row = self.table.currentRow()
        if not (0 <= row < len(self._entries)):
            return
        self._entries[row][field] = value
        col_map = {
            SWITCH_WIFI_ENTRY_SSID_FIELD: 0,
            SWITCH_WIFI_ENTRY_SECURITY_FIELD: 1,
            SWITCH_WIFI_ENTRY_PASSWORD_FIELD: 2,
        }
        col = col_map.get(field)
        if col is not None:
            item = self.table.item(row, col)
            if item is not None:
                item.setText(value)


class SwitchWifiCsvPreview(QWidget):
    """Simple read-only widget that previews a subset of rows from a switch Wi-Fi CSV."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.info_label = QLabel("CSV preview:", self)
        layout.addWidget(self.info_label)

        self.table = QTableWidget(self)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def update_entries(self, entries: Sequence[Mapping[str, Any]]) -> None:
        """Convenience helper: render entries list as a 3-column table."""
        headers = ["SSID", "Security Mode", "Password"]
        rows: list[list[Any]] = []
        for entry in entries or []:
            rows.append(
                [
                    str(entry.get(SWITCH_WIFI_ENTRY_SSID_FIELD, "") or ""),
                    str(entry.get(SWITCH_WIFI_ENTRY_SECURITY_FIELD, "") or ""),
                    str(entry.get(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, "") or ""),
                ]
            )
        self.set_preview_rows(headers, rows)

    def set_preview_rows(self, headers: Sequence[str], rows: Sequence[Sequence[Any]], limit: int = 20) -> None:
        """Display up to ``limit`` rows from the CSV with the given headers."""
        self.table.clear()
        self.table.setRowCount(0)
        if not headers:
            return
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels([str(h) for h in headers])
        max_rows = min(limit, len(rows))
        self.table.setRowCount(max_rows)
        for row_idx in range(max_rows):
            for col_idx, value in enumerate(rows[row_idx]):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)


def sync_switch_wifi_on_csv_changed(page: Any, new_path: str | None) -> None:
    """Sync switch_wifi UI when the global Execution CSV combo changes.

    When the current stability script is ``test_switch_wifi`` and the
    \"Use router configuration\" checkbox is checked, changes to the main
    Execution CSV combo should also update the router CSV selector and the
    Wi‑Fi list table so that the user always sees the SSID list for the
    effective CSV.
    """
    if not new_path:
        return
    try:
        case_path = getattr(page, "_current_case_path", "") or ""
        config_ctl = getattr(page, "config_ctl", None)
        if case_path and config_ctl is not None and hasattr(config_ctl, "script_case_key"):
            script_key = config_ctl.script_case_key(case_path)
        else:
            script_key = ""
    except Exception:
        script_key = ""
    if script_key != "switch_wifi":
        return

    field_widgets = getattr(page, "field_widgets", {}) or {}
    use_router = (
        field_widgets.get("stability.cases.switch_wifi.use_router")
        or field_widgets.get("cases.test_switch_wifi.use_router")
    )
    router_csv = (
        field_widgets.get("stability.cases.switch_wifi.router_csv")
        or field_widgets.get("cases.test_switch_wifi.router_csv")
    )
    wifi_list = (
        field_widgets.get("stability.cases.switch_wifi.manual_entries")
        or field_widgets.get("cases.test_switch_wifi.manual_entries")
    )

    is_router_mode = bool(isinstance(use_router, QCheckBox) and use_router.isChecked())
    if not is_router_mode:
        return

    config_ctl = getattr(page, "config_ctl", None)
    # 1) Try to keep the router_csv combo selection aligned with new_path.
    if isinstance(router_csv, ComboBox) and config_ctl is not None:
        try:
            normalized = config_ctl.normalize_csv_path(new_path)
            idx = config_ctl.find_csv_index(normalized, router_csv)
        except Exception:
            idx = -1
        if idx >= 0:
            try:
                with QSignalBlocker(router_csv):
                    router_csv.setCurrentIndex(idx)
            except Exception:
                logging.debug(
                    "Failed to sync switch_wifi router_csv from Execution CSV change",
                    exc_info=True,
                )

    # 2) Refresh the Wi‑Fi list table entries.
    if isinstance(wifi_list, SwitchWifiManualEditor) and config_ctl is not None:
        try:
            entries = config_ctl.load_switch_wifi_entries(new_path)
        except Exception:
            entries = []
        wifi_list.set_entries(entries)


def handle_switch_wifi_use_router_changed(page: Any, checked: bool) -> None:
    """Handle toggling of the 'Use router configuration' checkbox for switch_wifi."""
    field_widgets = getattr(page, "field_widgets", {}) or {}
    use_router = (
        field_widgets.get("stability.cases.switch_wifi.use_router")
        or field_widgets.get("cases.test_switch_wifi.use_router")
    )
    router_csv = (
        field_widgets.get("stability.cases.switch_wifi.router_csv")
        or field_widgets.get("cases.test_switch_wifi.router_csv")
    )
    wifi_list = (
        field_widgets.get("stability.cases.switch_wifi.manual_entries")
        or field_widgets.get("cases.test_switch_wifi.manual_entries")
    )

    # 1) Enable/disable + show/hide router_csv combo based on the mode.
    if router_csv is not None:
        if hasattr(router_csv, "setEnabled"):
            router_csv.setEnabled(bool(checked))
        if hasattr(router_csv, "setVisible"):
            router_csv.setVisible(bool(checked))

    # 2) When router mode is enabled, load entries from the currently selected CSV.
    if checked and router_csv is not None and hasattr(router_csv, "currentIndex"):
        try:
            idx = router_csv.currentIndex()
        except Exception:
            idx = -1
        if idx >= 0 and hasattr(router_csv, "itemData"):
            data = router_csv.itemData(idx)
            csv_path = data if isinstance(data, str) and data else router_csv.currentText()
            config_ctl = getattr(page, "config_ctl", None)
            if config_ctl is not None:
                try:
                    config_ctl.set_selected_csv(csv_path, sync_combo=True)
                except Exception:
                    logging.debug(
                        "Failed to sync selected CSV for switch_wifi router mode",
                        exc_info=True,
                    )
            signal = getattr(page, "csvFileChanged", None)
            if signal is not None and hasattr(signal, "emit"):
                try:
                    signal.emit(csv_path or "")
                except Exception:
                    logging.debug(
                        "Failed to emit csvFileChanged for switch_wifi router mode",
                        exc_info=True,
                    )
            if isinstance(wifi_list, SwitchWifiManualEditor) and config_ctl is not None:
                entries = config_ctl.load_switch_wifi_entries(csv_path)
                wifi_list.set_entries(entries)
            config_ctl = getattr(page, "config_ctl", None)
            if config_ctl is not None:
                try:
                    setattr(page, "_router_config_active", bool(csv_path))
                    config_ctl.update_rvr_nav_button()
                except Exception:
                    logging.debug("Failed to update RVR nav button for switch_wifi", exc_info=True)


def handle_switch_wifi_router_csv_changed(page: Any, index: int) -> None:
    """Handle router CSV combo index change in the switch_wifi stability section."""
    field_widgets = getattr(page, "field_widgets", {}) or {}
    router_csv = (
        field_widgets.get("stability.cases.switch_wifi.router_csv")
        or field_widgets.get("cases.test_switch_wifi.router_csv")
    )
    wifi_list = (
        field_widgets.get("stability.cases.switch_wifi.manual_entries")
        or field_widgets.get("cases.test_switch_wifi.manual_entries")
    )
    use_router = (
        field_widgets.get("stability.cases.switch_wifi.use_router")
        or field_widgets.get("cases.test_switch_wifi.use_router")
    )
    is_router_mode = bool(isinstance(use_router, QCheckBox) and use_router.isChecked())
    if not is_router_mode:
        return
    if router_csv is None or not hasattr(router_csv, "itemData"):
        return
    if index < 0:
        return
    data = router_csv.itemData(index)
    csv_path = data if isinstance(data, str) and data else router_csv.currentText()

    config_ctl = getattr(page, "config_ctl", None)
    if config_ctl is not None:
        try:
            config_ctl.set_selected_csv(csv_path, sync_combo=True)
        except Exception:
            logging.debug("Failed to sync selected_csv_path from switch_wifi router_csv", exc_info=True)
    signal = getattr(page, "csvFileChanged", None)
    if signal is not None and hasattr(signal, "emit"):
        try:
            signal.emit(csv_path or "")
        except Exception:
            logging.debug("Failed to emit csvFileChanged from switch_wifi", exc_info=True)

    if isinstance(wifi_list, SwitchWifiManualEditor) and config_ctl is not None:
        entries = config_ctl.load_switch_wifi_entries(csv_path)
        wifi_list.set_entries(entries)
    if config_ctl is not None:
        try:
            setattr(page, "_router_config_active", bool(csv_path))
            config_ctl.update_rvr_nav_button()
        except Exception:
            logging.debug("Failed to update RVR nav button for switch_wifi CSV change", exc_info=True)


def init_switch_wifi_actions(page: Any) -> None:
    """Wire test_switch_wifi Stability case controls to the unified dispatcher."""
    field_widgets = getattr(page, "field_widgets", {}) or {}

    use_router = (
        field_widgets.get("stability.cases.switch_wifi.use_router")
        or field_widgets.get("cases.test_switch_wifi.use_router")
    )
    router_csv = (
        field_widgets.get("stability.cases.switch_wifi.router_csv")
        or field_widgets.get("cases.test_switch_wifi.router_csv")
    )
    wifi_list = (
        field_widgets.get("stability.cases.switch_wifi.manual_entries")
        or field_widgets.get("cases.test_switch_wifi.manual_entries")
    )

    # Reuse Execution CSV behaviour for the router_csv combo:
    # entries come from performance CSV directory, and we disable the
    # \"Select config csv file\" placeholder for switch_wifi.
    if isinstance(router_csv, ComboBox):
        router_csv.setProperty("switch_wifi_include_placeholder", False)
        config_ctl = getattr(page, "config_ctl", None)
        if config_ctl is not None:
            try:
                config_ctl.refresh_registered_csv_combos()
            except Exception:
                logging.debug("refresh_registered_csv_combos failed for switch_wifi", exc_info=True)

    # Hook up checkbox to dispatcher entrypoint.
    if isinstance(use_router, QCheckBox):
        def _on_use_router_toggled(checked: bool) -> None:
            from src.ui.view.config.actions import handle_config_event  # local import to avoid cycles

            handle_config_event(
                page,
                "switch_wifi_use_router_changed",
                checked=bool(checked),
            )

        use_router.toggled.connect(_on_use_router_toggled)
        _on_use_router_toggled(use_router.isChecked())

    # Router CSV combo: when selection changes, update Wi‑Fi list from CSV.
    if router_csv is not None and hasattr(router_csv, "currentIndexChanged"):
        def _on_router_csv_index_changed(index: int) -> None:
            from src.ui.view.config.actions import handle_config_event  # local import to avoid cycles

            handle_config_event(
                page,
                "switch_wifi_router_csv_changed",
                index=int(index),
            )

        router_csv.currentIndexChanged.connect(_on_router_csv_index_changed)


__all__ = [
    "SwitchWifiManualEditor",
    "SwitchWifiCsvPreview",
    "sync_switch_wifi_on_csv_changed",
    "handle_switch_wifi_use_router_changed",
    "handle_switch_wifi_router_csv_changed",
    "init_switch_wifi_actions",
]
