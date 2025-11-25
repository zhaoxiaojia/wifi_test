"""Switch Wi-Fi specific widgets and helpers for the Config page."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from PyQt5.QtCore import Qt, QSignalBlocker, QSize
from PyQt5.QtWidgets import QCheckBox, QHBoxLayout, QVBoxLayout, QWidget, QSizePolicy
from qfluentwidgets import ComboBox

from src.util.constants import (
    AUTH_OPTIONS,
    SWITCH_WIFI_ENTRY_PASSWORD_FIELD,
    SWITCH_WIFI_ENTRY_SECURITY_FIELD,
    SWITCH_WIFI_ENTRY_SSID_FIELD,
    SWITCH_WIFI_MANUAL_ENTRIES_FIELD,
)
from src.ui import FormListPage, RouterConfigForm


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

    def __init__(self, parent: QWidget | None = None) -> None:
        from src.ui.view.theme import apply_theme as _apply_theme  # local to avoid cycles

        super().__init__(parent)
        _apply_theme(self, recursive=True)
        self.setObjectName("switchWifiConfigPage")
        # 水平填充父布局，高度依据 sizeHint，避免占满整列。
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
        self.form.rowChanged.connect(self._on_form_row_changed)
        self.form.addRequested.connect(self._on_form_add_requested)
        self.form.deleteRequested.connect(self._on_form_delete_requested)
        self.list.currentRowChanged.connect(self._on_list_row_changed)

        # Initialise form from first row when available.
        if self.rows:
            self.list.set_current_row(0)
            self.form.load_row(self.rows[0])

    # ------------------------------------------------------------------
    # QWidget sizing helpers
    # ------------------------------------------------------------------

    def sizeHint(self) -> QSize:  # type: ignore[override]
        """Constrain height so the Wi‑Fi list shows about 6–7 rows.

        The underlying table仍然带垂直滚动条，多余行通过滚动查看，避免脚本区留白过多。
        """
        base = super().sizeHint()
        width = base.width() if base.isValid() else 0
        if width < 300:
            width = 400

        # 估算列表高度：表头 + N 行 + 适当内边距
        try:
            table = self.list.table  # type: ignore[attr-defined]
            vh = table.verticalHeader()
            hh = table.horizontalHeader()
            row_height = vh.defaultSectionSize() if vh is not None else 28
            header_height = hh.height() if hh is not None else 24
        except Exception:  # pragma: no cover - defensive
            row_height = 28
            header_height = 24
        # 可见行数：1~7 行之间
        visible_rows = len(getattr(self, "rows", []) or [])
        if visible_rows <= 0:
            visible_rows = 1
        visible_rows = min(visible_rows, 7)
        height = header_height + row_height * visible_rows + 32  # 额外留少量 padding
        # 给一个下限，避免过于紧凑影响操作
        if height < 180:
            height = 180
        return QSize(width, height)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        parent = self.parentWidget()
        layout = parent.layout() if parent else None
        # 淇濈暀绠€鍗曠殑鐖跺竷灞€璋冩暣閫昏緫锛屼笉鍐嶈緭鍑鸿缁嗚皟璇曚俊鎭€?        _ = layout  # silence linters

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

    def _on_list_row_changed(self, row_index: int) -> None:
        if not (0 <= row_index < len(self.rows)):
            return
        self.form.load_row(self.rows[row_index])

    def _on_form_row_changed(self, data: dict[str, str]) -> None:
        row_index = self.list.current_row()
        if not (0 <= row_index < len(self.rows)):
            return
        self.rows[row_index].update(
            {
                SWITCH_WIFI_ENTRY_SSID_FIELD: data.get("ssid", ""),
                SWITCH_WIFI_ENTRY_SECURITY_FIELD: data.get("security_mode", ""),
                SWITCH_WIFI_ENTRY_PASSWORD_FIELD: data.get("password", ""),
            }
        )
        self.list.update_row(row_index, self.rows[row_index])

    def _on_form_add_requested(self, data: dict[str, str]) -> None:
        entry = {
            SWITCH_WIFI_ENTRY_SSID_FIELD: data.get("ssid", "").strip(),
            SWITCH_WIFI_ENTRY_SECURITY_FIELD: data.get("security_mode", "").strip(),
            SWITCH_WIFI_ENTRY_PASSWORD_FIELD: data.get("password", ""),
        }
        if not entry[SWITCH_WIFI_ENTRY_SSID_FIELD]:
            return
        self.rows.append(entry)
        self.list.set_rows(self.rows)
        new_index = len(self.rows) - 1
        if new_index >= 0:
            self.list.set_current_row(new_index)

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


def _resolve_switch_wifi_widgets(page: Any) -> tuple[Any, Any, Any]:
    """Helper to resolve switch_wifi widgets from the page field map."""
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
    return use_router, router_csv, wifi_list


def sync_switch_wifi_on_csv_changed(page: Any, new_path: str | None) -> None:
    """Sync switch_wifi UI when the global Execution CSV combo changes."""
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

    use_router, router_csv, wifi_list = _resolve_switch_wifi_widgets(page)
    is_router_mode = bool(isinstance(use_router, QCheckBox) and use_router.isChecked())
    if not is_router_mode:
        return

    config_ctl = getattr(page, "config_ctl", None)
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

    if isinstance(wifi_list, SwitchWifiConfigPage) and config_ctl is not None:
        try:
            entries = config_ctl.load_switch_wifi_entries(new_path)
        except Exception:
            entries = []
        # 仅刷新展示，不写回配置，避免覆盖 YAML。
        wifi_list.set_entries(entries)
    use_router, router_csv, wifi_list = _resolve_switch_wifi_widgets(page)
    is_router_mode = bool(isinstance(use_router, QCheckBox) and use_router.isChecked())
    if not is_router_mode:
        return

    config_ctl = getattr(page, "config_ctl", None)
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

    if isinstance(wifi_list, SwitchWifiConfigPage) and config_ctl is not None:
        try:
            entries = config_ctl.load_switch_wifi_entries(new_path)
        except Exception:
            entries = []
        # 仅刷新展示，不写回配置，避免覆盖 YAML。
        wifi_list.set_entries(entries)


def handle_switch_wifi_use_router_changed(page: Any, checked: bool) -> None:
    """Handle toggling of the 'Use router configuration' checkbox for switch_wifi."""
    use_router, router_csv, wifi_list = _resolve_switch_wifi_widgets(page)

    if router_csv is not None:
        if hasattr(router_csv, "setEnabled"):
            router_csv.setEnabled(bool(checked))
        if hasattr(router_csv, "setVisible"):
            router_csv.setVisible(bool(checked))

    config_ctl = getattr(page, "config_ctl", None)
    csv_path: str | None = None

    if checked and router_csv is not None and hasattr(router_csv, "currentIndex"):
        try:
            idx = router_csv.currentIndex()
        except Exception:
            idx = -1
        if idx >= 0 and hasattr(router_csv, "itemData"):
            data = router_csv.itemData(idx)
            csv_path = data if isinstance(data, str) and data else router_csv.currentText()
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
            # Router 模式下仅展示 CSV 内容，不写回配置。
            if isinstance(wifi_list, SwitchWifiConfigPage) and config_ctl is not None:
                try:
                    entries = config_ctl.load_switch_wifi_entries(csv_path)
                except Exception:
                    entries = []
                wifi_list.set_entries(entries)
    else:
        # 退出 router 模式时，列表回退到稳定性配置中的 manual_entries。
        if isinstance(wifi_list, SwitchWifiConfigPage):
            cfg = getattr(page, "config", {}) or {}
            stability = cfg.get("stability", {}) if isinstance(cfg, dict) else {}
            cases = stability.get("cases", {}) if isinstance(stability, dict) else {}
            case_cfg = cases.get("test_switch_wifi", {}) if isinstance(cases, dict) else {}
            entries = case_cfg.get(SWITCH_WIFI_MANUAL_ENTRIES_FIELD, [])
            wifi_list.set_entries(entries)
    if config_ctl is not None:
        try:
            setattr(page, "_router_config_active", bool(csv_path))
            config_ctl.update_rvr_nav_button()
        except Exception:
            logging.debug("Failed to update RVR nav button for switch_wifi", exc_info=True)


def handle_switch_wifi_router_csv_changed(page: Any, index: int) -> None:
    """Handle router CSV combo index change in the switch_wifi stability section."""
    use_router, router_csv, wifi_list = _resolve_switch_wifi_widgets(page)
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

    if isinstance(wifi_list, SwitchWifiConfigPage) and config_ctl is not None:
        try:
            entries = config_ctl.load_switch_wifi_entries(new_path)
        except Exception:
            entries = []
        # 仅刷新展示，不写回配置，避免覆盖 YAML。
        wifi_list.set_entries(entries)
    if config_ctl is not None:
        try:
            setattr(page, "_router_config_active", bool(csv_path))
            config_ctl.update_rvr_nav_button()
        except Exception:
            logging.debug("Failed to update RVR nav button for switch_wifi CSV change", exc_info=True)


def init_switch_wifi_actions(page: Any) -> None:
    """Wire test_switch_wifi Stability case controls to the unified dispatcher."""
    _use_router, router_csv, _wifi_list = _resolve_switch_wifi_widgets(page)

    if isinstance(router_csv, ComboBox):
        router_csv.setProperty("switch_wifi_include_placeholder", False)
        config_ctl = getattr(page, "config_ctl", None)
        if config_ctl is not None:
            try:
                config_ctl.refresh_registered_csv_combos()
            except Exception:
                logging.debug("refresh_registered_csv_combos failed for switch_wifi", exc_info=True)

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
    "normalize_switch_wifi_manual_entries",
    "SwitchWifiConfigPage",
    "sync_switch_wifi_on_csv_changed",
    "handle_switch_wifi_use_router_changed",
    "handle_switch_wifi_router_csv_changed",
    "init_switch_wifi_actions",
]




