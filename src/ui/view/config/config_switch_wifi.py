"""Switch Wi-Fi specific widgets and helpers for the Config page."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from PyQt5.QtCore import Qt, QSignalBlocker, QSize, pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QHBoxLayout, QVBoxLayout, QWidget, QSizePolicy
from qfluentwidgets import ComboBox

from src.util.constants import (
    AUTH_OPTIONS,
    OPEN_AUTH,
    SWITCH_WIFI_CASE_KEY,
    SWITCH_WIFI_CASE_KEYS,
    SWITCH_WIFI_ENTRY_PASSWORD_FIELD,
    SWITCH_WIFI_ENTRY_SECURITY_FIELD,
    SWITCH_WIFI_ENTRY_SSID_FIELD,
    SWITCH_WIFI_MANUAL_ENTRIES_FIELD,
)
from src.ui.view import FormListPage, RouterConfigForm, FormListBinder


def normalize_switch_wifi_manual_entries(entries: Any) -> list[dict[str, str]]:
    """Normalise manual Wi-Fi entries for switch Wi-Fi stability tests."""
    normalized: list[dict[str, str]] = []
    if isinstance(entries, Sequence) and not isinstance(entries, (str, bytes)):
        for item in entries:
            if not isinstance(item, Mapping):
                continue
            ssid = str(item.get(SWITCH_WIFI_ENTRY_SSID_FIELD, "") or "").strip()
            mode = str(
                item.get(SWITCH_WIFI_ENTRY_SECURITY_FIELD, AUTH_OPTIONS[0])
                or AUTH_OPTIONS[0]
            ).strip()
            if mode not in AUTH_OPTIONS:
                mode = AUTH_OPTIONS[0]
            password = str(item.get(SWITCH_WIFI_ENTRY_PASSWORD_FIELD, "") or "")
            normalized.append(
                {
                    SWITCH_WIFI_ENTRY_SSID_FIELD: ssid,
                    SWITCH_WIFI_ENTRY_SECURITY_FIELD: mode,
                    SWITCH_WIFI_ENTRY_PASSWORD_FIELD: password,
                }
            )
    return normalized


class SwitchWifiConfigPage(QWidget):
    """In-memory Wi-Fi list editor for switch_wifi manual_entries."""

    # Emitted whenever the underlying manual_entries list changes due to
    # user actions (add/delete/edit). Controllers can hook this to trigger
    # autosave without relying on internal widget details.
    entriesChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        from src.ui.view.theme import apply_theme as _apply_theme  # local to avoid cycles

        super().__init__(parent)
        _apply_theme(self, recursive=True)
        self.setObjectName("switchWifiConfigPage")

        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setSizePolicy(size_policy)

        self.headers: list[str] = [
            SWITCH_WIFI_ENTRY_SSID_FIELD,
            SWITCH_WIFI_ENTRY_SECURITY_FIELD,
            SWITCH_WIFI_ENTRY_PASSWORD_FIELD,
        ]
        self.rows: list[dict[str, str]] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        content = QWidget(self)
        layout = QHBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        outer.addWidget(content, 1)

        # Form limited to SSID / security / password fields.
        self.form = RouterConfigForm(
            router=None,
            fields=("ssid", "security_mode", "password"),
            parent=content,
        )
        layout.addWidget(self.form, 2)

        self.list = FormListPage(self.headers, self.rows, checkable=False, parent=content)
        layout.addWidget(self.list, 5)

        # Wire interactions.
        self._binder = FormListBinder(
            form=self.form,
            list_widget=self.list,
            rows=self.rows,
            on_rows_changed=lambda _rows: self.entriesChanged.emit(),
            bind_add=False,
            bind_delete=False,
        )
        self.form.addRequested.connect(self._on_form_add_requested)
        self.form.deleteRequested.connect(self._on_form_delete_requested)

        # Initialise form from first row when available.
        if self.rows:
            self.list.set_current_row(0)
            self.form.load_row(self.rows[0])

    # ------------------------------------------------------------------
    # QWidget sizing helpers
    # ------------------------------------------------------------------

    def sizeHint(self) -> QSize:  # type: ignore[override]
        """Constrain height so the Wi-Fi list shows about 6–7 rows."""
        base = super().sizeHint()
        width = base.width() if base.isValid() else 0
        if width < 300:
            width = 400

        table = self.list.table  # type: ignore[attr-defined]
        vh = table.verticalHeader()
        hh = table.horizontalHeader()
        row_height = vh.defaultSectionSize() if vh is not None else 28
        header_height = hh.height() if hh is not None else 24

        visible_rows = len(self.rows)
        if visible_rows <= 0:
            visible_rows = 1
        visible_rows = min(visible_rows, 7)
        height = header_height + row_height * visible_rows + 32
        if height < 180:
            height = 180
        return QSize(width, height)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_entries(self, entries: Sequence[Mapping[str, Any]] | None) -> None:
        """Replace the underlying entry list and refresh the UI."""
        self.rows = normalize_switch_wifi_manual_entries(entries)
        self.list.set_data(self.headers, self.rows)
        if self.rows:
            self.list.set_current_row(0)
            self.form.load_row(self.rows[0])
        else:
            self.form.reset_form()

    def entries(self) -> list[dict[str, str]]:
        """Return a deep copy of current entries."""
        return [dict(e) for e in self.rows]

    def serialize(self) -> list[dict[str, str]]:
        """Return entries in config-friendly format."""
        return self.entries()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_form_add_requested(self, data: dict[str, str]) -> None:
        entry = {
            SWITCH_WIFI_ENTRY_SSID_FIELD: data.get("ssid", "").strip(),
            SWITCH_WIFI_ENTRY_SECURITY_FIELD: data.get("security_mode", "").strip(),
            SWITCH_WIFI_ENTRY_PASSWORD_FIELD: data.get("password", ""),
        }
        ssid = entry[SWITCH_WIFI_ENTRY_SSID_FIELD]
        security = entry[SWITCH_WIFI_ENTRY_SECURITY_FIELD]
        password = entry[SWITCH_WIFI_ENTRY_PASSWORD_FIELD]
        if not ssid:
            return
        # For non-open security modes, require a non-empty password so that
        # the configuration is usable.
        if security and security not in OPEN_AUTH and not password:
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "Password required",
                "Please enter a password for the selected security mode.",
            )
            return
        self.rows.append(entry)
        self.list.set_rows(self.rows)
        new_index = len(self.rows) - 1
        if new_index >= 0:
            self.list.set_current_row(new_index)
        self.entriesChanged.emit()

    def _on_form_delete_requested(self) -> None:
        row_index = self.list.current_row()
        if not (0 <= row_index < len(self.rows)):
            return
        del self.rows[row_index]
        self.list.set_rows(self.rows)
        if self.rows:
            new_index = min(row_index, len(self.rows) - 1)
            self.list.set_current_row(new_index)
            self.form.load_row(self.rows[new_index])
        else:
            self.form.reset_form()
        self.entriesChanged.emit()


def _resolve_switch_wifi_widgets(page: Any) -> tuple[Any, Any, Any]:
    """Helper to resolve switch_wifi widgets from the page field map."""
    field_widgets = page.field_widgets
    use_router = (
        field_widgets.get(f"stability.cases.{SWITCH_WIFI_CASE_KEY}.use_router")
        or field_widgets.get(f"cases.{SWITCH_WIFI_CASE_KEY}.use_router")
        or field_widgets.get("stability.cases.switch_wifi.use_router")
        or field_widgets.get("cases.test_switch_wifi.use_router")
    )
    router_csv = (
        field_widgets.get(f"stability.cases.{SWITCH_WIFI_CASE_KEY}.router_csv")
        or field_widgets.get(f"cases.{SWITCH_WIFI_CASE_KEY}.router_csv")
        or field_widgets.get("stability.cases.switch_wifi.router_csv")
        or field_widgets.get("cases.test_switch_wifi.router_csv")
    )
    wifi_list = (
        field_widgets.get(f"stability.cases.{SWITCH_WIFI_CASE_KEY}.manual_entries")
        or field_widgets.get(f"cases.{SWITCH_WIFI_CASE_KEY}.manual_entries")
        or field_widgets.get("stability.cases.switch_wifi.manual_entries")
        or field_widgets.get("cases.test_switch_wifi.manual_entries")
    )
    return use_router, router_csv, wifi_list


def sync_switch_wifi_on_csv_changed(page: Any, new_path: str | None) -> None:
    """Sync switch_wifi UI when the global Execution CSV combo changes."""
    if not new_path:
        return
    case_path = page._current_case_path or ""
    script_key = page.config_ctl.script_case_key(case_path) if case_path else ""
    if script_key not in SWITCH_WIFI_CASE_KEYS:
        return

    use_router, router_csv, wifi_list = _resolve_switch_wifi_widgets(page)
    is_router_mode = bool(isinstance(use_router, QCheckBox) and use_router.isChecked())
    if not is_router_mode:
        return

    config_ctl = page.config_ctl
    if isinstance(router_csv, ComboBox):
        normalized = config_ctl.normalize_csv_path(new_path)
        idx = config_ctl.find_csv_index(normalized, router_csv)
        if idx >= 0:
            with QSignalBlocker(router_csv):
                router_csv.setCurrentIndex(idx)

    if isinstance(wifi_list, SwitchWifiConfigPage):
        entries = config_ctl.load_switch_wifi_entries(new_path)
        wifi_list.set_entries(entries)


def handle_switch_wifi_use_router_changed(page: Any, checked: bool) -> None:
    """Handle toggling of the 'Use router configuration' checkbox for switch_wifi."""
    use_router, router_csv, wifi_list = _resolve_switch_wifi_widgets(page)

    if isinstance(router_csv, ComboBox):
        router_csv.setEnabled(bool(checked))
        router_csv.setVisible(bool(checked))

    config_ctl = page.config_ctl
    csv_path: str | None = None

    if checked and isinstance(router_csv, ComboBox):
        idx = router_csv.currentIndex()
        if idx >= 0:
            data = router_csv.itemData(idx)
            csv_path = data if isinstance(data, str) and data else router_csv.currentText()
            config_ctl.set_selected_csv(csv_path, sync_combo=True)
            page.csvFileChanged.emit(csv_path or "")
            if isinstance(wifi_list, SwitchWifiConfigPage):
                entries = config_ctl.load_switch_wifi_entries(csv_path)
                wifi_list.set_entries(entries)
    else:
        if isinstance(wifi_list, SwitchWifiConfigPage):
            cfg = page.config
            stability = cfg.get("stability", {})
            cases = stability.get("cases", {})
            case_cfg = (
                cases.get(SWITCH_WIFI_CASE_KEY)
                or cases.get("test_switch_wifi")
                or cases.get("switch_wifi")
                or {}
            )
            entries = case_cfg.get(SWITCH_WIFI_MANUAL_ENTRIES_FIELD, [])
            wifi_list.set_entries(entries)

    page._router_config_active = bool(csv_path)
    config_ctl.update_rvr_nav_button()


def handle_switch_wifi_router_csv_changed(page: Any, index: int) -> None:
    """Handle router CSV combo index change in the switch_wifi stability section."""
    use_router, router_csv, wifi_list = _resolve_switch_wifi_widgets(page)
    is_router_mode = bool(isinstance(use_router, QCheckBox) and use_router.isChecked())
    if not is_router_mode:
        return
    if not isinstance(router_csv, ComboBox):
        return
    if index < 0:
        return

    data = router_csv.itemData(index)
    csv_path = data if isinstance(data, str) and data else router_csv.currentText()

    config_ctl = page.config_ctl
    config_ctl.set_selected_csv(csv_path, sync_combo=True)
    page.csvFileChanged.emit(csv_path or "")

    if isinstance(wifi_list, SwitchWifiConfigPage):
        entries = config_ctl.load_switch_wifi_entries(csv_path)
        wifi_list.set_entries(entries)

    page._router_config_active = bool(csv_path)
    config_ctl.update_rvr_nav_button()


def init_switch_wifi_actions(page: Any) -> None:
    """Wire test_switch_wifi stability case controls to the unified dispatcher."""
    use_router, router_csv, _wifi_list = _resolve_switch_wifi_widgets(page)

    if isinstance(router_csv, ComboBox):
        router_csv.setProperty("switch_wifi_include_placeholder", False)
    page.config_ctl.refresh_registered_csv_combos()

    use_router, router_csv, _wifi_list = _resolve_switch_wifi_widgets(page)
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

    if isinstance(router_csv, ComboBox):

        def _on_router_csv_index_changed(index: int) -> None:
            from src.ui.view.config.actions import handle_config_event  # local import to avoid cycles

            handle_config_event(
                page,
                "switch_wifi_router_csv_changed",
                index=int(index),
            )

        router_csv.currentIndexChanged.connect(_on_router_csv_index_changed)


__all__ = [
    "normalize_switch_wifi_manual_entries",
    "SwitchWifiConfigPage",
    "sync_switch_wifi_on_csv_changed",
    "handle_switch_wifi_use_router_changed",
    "handle_switch_wifi_router_csv_changed",
    "init_switch_wifi_actions",
]
