"""Switch Wi-Fi specific editor widgets for the Config page."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from PyQt5.QtCore import Qt, QSignalBlocker
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import ComboBox, LineEdit, PushButton

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

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)

        self.ssid_edit = LineEdit(self)
        self.ssid_edit.setPlaceholderText("SSID")
        form.addRow("SSID", self.ssid_edit)

        self.security_combo = ComboBox(self)
        self.security_combo.addItems(AUTH_OPTIONS)
        self.security_combo.setMinimumWidth(160)
        form.addRow("Security", self.security_combo)

        self.password_edit = LineEdit(self)
        self.password_edit.setPlaceholderText("Password (optional)")
        form.addRow("Password", self.password_edit)

        layout.addLayout(form)

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
        entry = {
            SWITCH_WIFI_ENTRY_SSID_FIELD: self.ssid_edit.text().strip(),
            SWITCH_WIFI_ENTRY_SECURITY_FIELD: self.security_combo.currentText().strip(),
            SWITCH_WIFI_ENTRY_PASSWORD_FIELD: self.password_edit.text(),
        }
        if not entry[SWITCH_WIFI_ENTRY_SSID_FIELD]:
            return
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


__all__ = ["SwitchWifiManualEditor", "SwitchWifiCsvPreview"]

