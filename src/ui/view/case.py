"""Case (RvR Wi-Fi) configuration view.

This module hosts the *pure UI* for the RvR Wi-Fi case page.  The
business logic (CSV load/save, router capability, table<->form sync)
remains in :mod:`rvr_wifi_config`, which composes this view and wires
signals.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CardWidget, ComboBox, LineEdit, PushButton, TableWidget

from src.util.constants import AUTH_OPTIONS
from src.ui.view.theme import apply_theme, apply_font_and_selection


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

