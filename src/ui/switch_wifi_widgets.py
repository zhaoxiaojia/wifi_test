"""Switch Wi-Fi editing widgets."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from PyQt5.QtCore import Qt, QSignalBlocker, pyqtSignal
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
from .theme import (
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
    controls to add or remove rows.  Emits an ``entriesChanged`` signal when
    the underlying list of dictionaries representing the entries is updated.
    """

    entriesChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Initialize the class instance, set up initial state and construct UI widgets.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
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

    def set_entries(self, entries: Sequence[Mapping[str, Any]] | None) -> None:
        """
        Set the entries property on the instance.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        sanitized = []
        if isinstance(entries, Sequence):
            for item in entries:
                if not isinstance(item, Mapping):
                    continue
                sanitized.append(self._sanitize_entry(item))
        self._entries = sanitized
        self._refresh_table()
        if self._entries:
            self.table.setCurrentCell(0, 0)
        else:
            self._clear_form()

    def serialize(self) -> list[dict[str, str]]:
        """
        Serialize the current state into a configuration object for persistence.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        result: list[dict[str, str]] = []
        for item in self._entries:
            ssid = item.get(SWITCH_WIFI_ENTRY_SSID_FIELD, "").strip()
            if not ssid:
                continue
            mode = item.get(SWITCH_WIFI_ENTRY_SECURITY_FIELD, AUTH_OPTIONS[0]) or AUTH_OPTIONS[0]
            password = item.get(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, "")
            result.append(
                {
                    SWITCH_WIFI_ENTRY_SSID_FIELD: ssid,
                    SWITCH_WIFI_ENTRY_SECURITY_FIELD: mode,
                    SWITCH_WIFI_ENTRY_PASSWORD_FIELD: password,
                }
            )
        return result

    def _sanitize_entry(self, item: Mapping[str, Any]) -> dict[str, str]:
        """
        Execute the sanitize entry routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        ssid = str(item.get(SWITCH_WIFI_ENTRY_SSID_FIELD, "") or "").strip()
        mode = str(
            item.get(SWITCH_WIFI_ENTRY_SECURITY_FIELD, AUTH_OPTIONS[0]) or AUTH_OPTIONS[0]
        ).strip()
        if mode not in AUTH_OPTIONS:
            mode = AUTH_OPTIONS[0]
        password = str(item.get(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, "") or "")
        return {
            SWITCH_WIFI_ENTRY_SSID_FIELD: ssid,
            SWITCH_WIFI_ENTRY_SECURITY_FIELD: mode,
            SWITCH_WIFI_ENTRY_PASSWORD_FIELD: password,
        }

    def _refresh_table(self) -> None:
        """
        Refresh the  table to ensure the UI is up to date.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self._loading = True
        try:
            self.table.setRowCount(len(self._entries))
            for row, item in enumerate(self._entries):
                self.table.setItem(
                    row,
                    0,
                    QTableWidgetItem(item.get(SWITCH_WIFI_ENTRY_SSID_FIELD, "")),
                )
                self.table.setItem(
                    row,
                    1,
                    QTableWidgetItem(item.get(SWITCH_WIFI_ENTRY_SECURITY_FIELD, "")),
                )
                self.table.setItem(
                    row,
                    2,
                    QTableWidgetItem(item.get(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, "")),
                )
        finally:
            self._loading = False

    def _clear_form(self) -> None:
        """
        Execute the clear form routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        with QSignalBlocker(self.ssid_edit):
            self.ssid_edit.setText("")
        with QSignalBlocker(self.password_edit):
            self.password_edit.setText("")
        with QSignalBlocker(self.security_combo):
            if self.security_combo.count():
                self.security_combo.setCurrentIndex(0)

    def _on_current_row_changed(self, row: int, _column: int, _prev_row: int, _prev_column: int) -> None:
        """
        Handle the current row changed event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if self._loading:
            return
        if 0 <= row < len(self._entries):
            entry = self._entries[row]
            with QSignalBlocker(self.ssid_edit):
                self.ssid_edit.setText(entry.get(SWITCH_WIFI_ENTRY_SSID_FIELD, ""))
            with QSignalBlocker(self.password_edit):
                self.password_edit.setText(entry.get(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, ""))
            with QSignalBlocker(self.security_combo):
                mode = entry.get(SWITCH_WIFI_ENTRY_SECURITY_FIELD, AUTH_OPTIONS[0])
                index = self.security_combo.findText(mode)
                if index < 0:
                    index = 0
                self.security_combo.setCurrentIndex(index)
        else:
            self._clear_form()

    def _update_current_entry(self, key: str, value: str) -> None:
        """
        Update the  current entry to reflect current data.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if self._loading:
            return
        row = self.table.currentRow()
        if not (0 <= row < len(self._entries)):
            return
        if key == SWITCH_WIFI_ENTRY_SECURITY_FIELD and value not in AUTH_OPTIONS:
            value = AUTH_OPTIONS[0]
        self._entries[row][key] = value
        if key == SWITCH_WIFI_ENTRY_SSID_FIELD:
            item = self.table.item(row, 0)
            if item is not None:
                item.setText(value)
        elif key == SWITCH_WIFI_ENTRY_SECURITY_FIELD:
            item = self.table.item(row, 1)
            if item is not None:
                item.setText(value)
        elif key == SWITCH_WIFI_ENTRY_PASSWORD_FIELD:
            item = self.table.item(row, 2)
            if item is not None:
                item.setText(value)
        self.entriesChanged.emit()

    def _on_add_entry(self) -> None:
        """
        Handle the add entry event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        new_entry = {
            SWITCH_WIFI_ENTRY_SSID_FIELD: "",
            SWITCH_WIFI_ENTRY_SECURITY_FIELD: AUTH_OPTIONS[0],
            SWITCH_WIFI_ENTRY_PASSWORD_FIELD: "",
        }
        self._entries.append(new_entry)
        self._refresh_table()
        if self._entries:
            self.table.setCurrentCell(len(self._entries) - 1, 0)
        self.entriesChanged.emit()

    def _on_delete_entry(self) -> None:
        """
        Handle the delete entry event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        row = self.table.currentRow()
        if not (0 <= row < len(self._entries)):
            return
        del self._entries[row]
        self._refresh_table()
        if self._entries:
            new_row = min(row, len(self._entries) - 1)
            self.table.setCurrentCell(new_row, 0)
        else:
            self._clear_form()
        self.entriesChanged.emit()


class SwitchWifiCsvPreview(QTableWidget):
    """
    Read‑only table view used to display Wi‑Fi credentials parsed from router
    configuration CSV files.

    Provides three columns (SSID, security mode and password) and disables
    editing and selection, serving purely as a preview.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Initialize the class instance, set up initial state and construct UI widgets.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["SSID", "Security Mode", "Password"])
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAlternatingRowColors(False)
        apply_font_and_selection(
            self,
            header_bg=SWITCH_WIFI_TABLE_HEADER_BG,
            header_fg=SWITCH_WIFI_TABLE_HEADER_FG,
            sel_bg=SWITCH_WIFI_TABLE_SELECTION_BG,
            sel_text=SWITCH_WIFI_TABLE_SELECTION_FG,
        )

    def update_entries(self, entries: Sequence[Mapping[str, Any]] | None) -> None:
        """
        Update the  entries to reflect current data.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.setRowCount(0)
        if not entries:
            return
        self.setRowCount(len(entries))
        for row, item in enumerate(entries):
            ssid = str(item.get(SWITCH_WIFI_ENTRY_SSID_FIELD, "") or "")
            mode = str(item.get(SWITCH_WIFI_ENTRY_SECURITY_FIELD, "") or "")
            password = str(item.get(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, "") or "")
            self.setItem(row, 0, QTableWidgetItem(ssid))
            self.setItem(row, 1, QTableWidgetItem(mode))
            self.setItem(row, 2, QTableWidgetItem(password))


