from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional

from PyQt5.QtCore import QSortFilterProxyModel
from PyQt5.QtWidgets import QCheckBox, QSpinBox, QDoubleSpinBox
from qfluentwidgets import ComboBox, LineEdit

from src.ui.model.rules import evaluate_all_rules
from src.ui.view.common import EditableInfo
from src.ui import load_config_page_state, save_config_page_state
from src import display_to_case_path
from src.util.constants import (
    SWITCH_WIFI_CASE_ALIASES,
    SWITCH_WIFI_CASE_KEY,
    SWITCH_WIFI_CASE_KEYS,
    SWITCH_WIFI_MANUAL_ENTRIES_FIELD,
    SWITCH_WIFI_ROUTER_CSV_FIELD,
    SWITCH_WIFI_USE_ROUTER_FIELD,
    TOOL_SECTION_KEY,
    WIFI_PRODUCT_PROJECT_MAP,
    TURN_TABLE_SECTION_KEY,
    TURN_TABLE_FIELD_IP_ADDRESS,
    TURN_TABLE_FIELD_STEP,
    TURN_TABLE_FIELD_STATIC_DB,
    TURN_TABLE_FIELD_TARGET_RSSI,
    get_config_base,
    get_src_base,
)
from src.ui.controller.case_ctl import (
    _load_csv_selection_from_config as _proxy_load_csv_selection_from_config,
    _resolve_csv_config_path as _proxy_resolve_csv_config_path,
    _update_csv_options as _proxy_update_csv_options,
    _capture_preselected_csv as _proxy_capture_preselected_csv,
    _normalize_csv_path as _proxy_normalize_csv_path,
    _relativize_config_path as _proxy_relativize_config_path,
    _find_csv_index as _proxy_find_csv_index,
    _set_selected_csv as _proxy_set_selected_csv,
    _populate_csv_combo as _proxy_populate_csv_combo,
    _refresh_registered_csv_combos as _proxy_refresh_registered_csv_combos,
    _load_switch_wifi_entries as _proxy_load_switch_wifi_entries,
    _update_switch_wifi_preview as _proxy_update_switch_wifi_preview,
    _update_rvr_nav_button as _proxy_update_rvr_nav_button,
    _open_rvr_wifi_config as _proxy_open_rvr_wifi_config,
)
from src.ui.view.common import ScriptConfigEntry, TestFileFilterModel, RfStepSegmentsWidget
from src.ui.view.config.config_switch_wifi import (
    normalize_switch_wifi_manual_entries,
    SwitchWifiConfigPage,
)
from src.ui.view.config.config_compatibility import (
    CompatibilityRelayEditor,
)
from src.ui.view.config.config_str import script_field_key
from src.ui.controller import show_info_bar
from src.ui.view.ui_adapter import UiEvent

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from src.ui.view.config.page import CaseConfigPage


class _ConnectTypeControllerMixin:
    """Connect-type specific configuration helpers."""

    def normalize_connect_type_section(self, raw_value: Any) -> dict[str, Any]:
        """Normalise connect_type section including Android/Linux/third_party."""
        source = raw_value if isinstance(raw_value, Mapping) else {}
        normalized: dict[str, Any] = {}

        type_value = source.get("type", "")
        type_value = str(type_value).strip() or "Android"
        lowered_type = type_value.lower()
        if lowered_type in {"android", "adb"}:
            type_value = "Android"
        elif lowered_type in {"linux", "telnet"}:
            type_value = "Linux"
        normalized["type"] = type_value

        android_cfg = source.get("Android")
        android_dict = dict(android_cfg)
        device = android_dict.get("device", "")
        android_dict["device"] = str(device).strip() if device is not None else ""
        normalized["Android"] = android_dict
        normalized.pop("adb", None)

        linux_cfg = source.get("Linux")
        linux_dict = dict(linux_cfg)
        telnet_ip = linux_dict.get("ip", "")
        linux_dict["ip"] = str(telnet_ip).strip() if telnet_ip is not None else ""
        wildcard = linux_dict.get("wildcard", "")
        linux_dict["wildcard"] = str(wildcard).strip() if wildcard is not None else ""
        normalized["Linux"] = linux_dict
        normalized.pop("telnet", None)

        third_cfg = source.get("third_party")
        third_dict = dict(third_cfg)
        enabled_val = third_dict.get("enabled", False)
        enabled_bool = bool(enabled_val)
        third_dict["enabled"] = enabled_bool
        wait_val = third_dict.get("wait_seconds")
        wait_seconds: Optional[int]
        wait_seconds = int(str(wait_val).strip()) if wait_val not in (None, "") else None
        third_dict["wait_seconds"] = wait_seconds if wait_seconds is None or wait_seconds > 0 else None
        normalized["third_party"] = third_dict

        return normalized


class _StabilityControllerMixin:
    """Stability-case specific helpers for defaults and settings."""

    def ensure_script_case_defaults(self, case_key: str, case_path: str) -> dict[str, Any]:
        """Ensure stability case defaults exist, handling legacy aliases."""
        page = self.page
        stability_cfg = page.config.setdefault("stability", {})
        cases_section = stability_cfg.setdefault("cases", {})
        entry = cases_section.get(case_key)
        if not isinstance(entry, dict):
            entry = None
        if case_key == SWITCH_WIFI_CASE_KEY and entry is None:
            for legacy_key in SWITCH_WIFI_CASE_ALIASES:
                legacy_entry = cases_section.get(legacy_key)
                if isinstance(legacy_entry, dict):
                    entry = dict(legacy_entry)
                    break
        if entry is None:
            entry = {}

        def _ensure_branch(name: str) -> None:
            branch = entry.get(name)
            if not isinstance(branch, dict):
                branch = {}
            branch.setdefault("enabled", False)
            branch.setdefault("on_duration", 0)
            branch.setdefault("off_duration", 0)
            branch.setdefault("relay_type", "usb_relay")
            branch.setdefault("relay_params", "")
            branch.setdefault("port", "")
            branch.setdefault("mode", "NO")
            entry[name] = branch

        if case_key == SWITCH_WIFI_CASE_KEY:
            entry.setdefault(SWITCH_WIFI_USE_ROUTER_FIELD, False)
            router_csv = entry.get(SWITCH_WIFI_ROUTER_CSV_FIELD)
            entry[SWITCH_WIFI_ROUTER_CSV_FIELD] = str(router_csv or "").strip()
            manual_entries = entry.get(SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
            entry[SWITCH_WIFI_MANUAL_ENTRIES_FIELD] = normalize_switch_wifi_manual_entries(
                manual_entries
            )
            _ensure_branch("ac")
            _ensure_branch("str")
            cases_section[case_key] = entry
            for legacy_key in SWITCH_WIFI_CASE_ALIASES:
                if legacy_key in cases_section:
                    cases_section.pop(legacy_key, None)
            return entry

        _ensure_branch("ac")
        _ensure_branch("str")
        cases_section[case_key] = entry
        return entry

    # (duplicate normalize_stability_settings removed here)

    def script_case_key(self, case_path: str | Path) -> str:
        """Return the logical script key used by stability config for the given case path."""
        path_obj = case_path if isinstance(case_path, Path) else Path(case_path)
        if path_obj.is_absolute():
            from src.util.constants import get_src_base

            path_obj = path_obj.resolve().relative_to(Path(get_src_base()).resolve())
        stem = path_obj.stem.lower()
        if stem in SWITCH_WIFI_CASE_KEYS:
            return SWITCH_WIFI_CASE_KEY
        return stem

    def is_stability_case(self, case_path: str | Path | None) -> bool:
        """Return True if the given case path is a stability testcase."""
        if not case_path:
            return False
        path_obj = case_path if isinstance(case_path, Path) else Path(case_path)
        parts = path_obj.as_posix().split("/")
        return "stability" in (p.lower() for p in parts)

    def is_performance_case(self, abs_case_path: str | Path | None) -> bool:
        """Return True if the given case path is a performance testcase."""
        if not abs_case_path:
            return False
        path_obj = abs_case_path if isinstance(abs_case_path, Path) else Path(abs_case_path)
        parts = path_obj.as_posix().split("/")
        return "performance" in (p.lower() for p in parts)


class _CsvRvrControllerMixin:
    """CSV / RvR helpers shared across Config UI."""

    def resolve_csv_config_path(self, value: Any) -> str | None:
        return _proxy_resolve_csv_config_path(value)

    def normalize_csv_path(self, path: Any) -> str | None:
        return _proxy_normalize_csv_path(path)

    def relativize_config_path(self, path: Any) -> str:
        return _proxy_relativize_config_path(path)

    def find_csv_index(self, normalized_path: str | None, combo=None) -> int:
        return _proxy_find_csv_index(self.page, normalized_path, combo)

    def set_selected_csv(self, path: str | None, *, sync_combo: bool = True) -> bool:
        return _proxy_set_selected_csv(self.page, path, sync_combo=sync_combo)

    def update_csv_options(self) -> None:
        _proxy_update_csv_options(self.page)

    def capture_preselected_csv(self) -> None:
        _proxy_capture_preselected_csv(self.page)

    def populate_csv_combo(
        self,
        combo,
        selected_path: str | None,
        *,
        include_placeholder: bool = False,
    ) -> None:
        _proxy_populate_csv_combo(
            self.page,
            combo,
            selected_path,
            include_placeholder=include_placeholder,
        )

    def refresh_registered_csv_combos(self) -> None:
        _proxy_refresh_registered_csv_combos(self.page)

    def load_switch_wifi_entries(self, csv_path: str | None) -> list[dict[str, str]]:
        return _proxy_load_switch_wifi_entries(self.page, csv_path)

    def update_switch_wifi_preview(self, preview, csv_path: str | None) -> None:
        _proxy_update_switch_wifi_preview(self.page, preview, csv_path)

    def update_rvr_nav_button(self) -> None:
        _proxy_update_rvr_nav_button(self.page)

    def open_rvr_wifi_config(self) -> None:
        _proxy_open_rvr_wifi_config(self.page)

    def reset_second_page_inputs(self) -> None:
        self.reset_second_page_model_state()
        self.reset_second_page_ui_state()

    def reset_second_page_model_state(self) -> None:
        page = self.page
        self.set_selected_csv(page.selected_csv_path, sync_combo=True)

    def reset_second_page_ui_state(self) -> None:
        page = self.page
        page.csv_combo.setEnabled(bool(page._enable_rvr_wifi))


class _RouterControllerMixin:
    """Router-related helpers for Config UI."""

    def handle_router_name_changed(self, name: str) -> None:
        page = self.page
        from src.tools.router_tool.router_factory import get_router  # type: ignore

        router_cfg = page.config.get("router", {})
        addr = router_cfg.get("address") if router_cfg.get("name") == name else None
        router_obj = get_router(name, addr)
        page.router_obj = router_obj
        router_addr_widget = page.field_widgets.get("router.address")
        router_addr_widget.setText(router_obj.address)
        self.update_csv_options()

    def handle_router_address_changed(self, address: str) -> None:
        page = self.page
        router_obj = page.router_obj
        router_obj.address = address
        self.update_csv_options()


class _EditableStateControllerMixin:
    """EditableInfo and run/lock helpers for Config UI."""

    def apply_editable_info(self, info: "EditableInfo | None") -> None:
        page = self.page
        if info is None:
            fields: set[str] = set()
            enable_csv = False
            enable_rvr_wifi = False
        else:
            fields = set(info.fields)
            enable_csv = info.enable_csv
            enable_rvr_wifi = info.enable_rvr_wifi
        snapshot = EditableInfo(
            fields=fields,
            enable_csv=enable_csv,
            enable_rvr_wifi=enable_rvr_wifi,
        )
        page._last_editable_info = snapshot
        self._apply_editable_model_state(snapshot)
        self._apply_editable_ui_state(snapshot)

    def _apply_editable_model_state(self, snapshot: "EditableInfo") -> None:
        page = self.page
        page._enable_rvr_wifi = snapshot.enable_rvr_wifi
        page._router_config_active = False if not snapshot.enable_rvr_wifi else page._router_config_active
        self.set_selected_csv(page.selected_csv_path, sync_combo=True) if snapshot.enable_csv else self.set_selected_csv(None, sync_combo=False)

    def _apply_editable_ui_state(self, snapshot: "EditableInfo") -> None:
        page = self.page
        page.csv_combo.setEnabled(True)
        self.update_rvr_nav_button()
        main_window = page.window()
        rvr_page = main_window.rvr_wifi_config_page
        rvr_page.set_case_content_visible(bool(snapshot.enable_rvr_wifi))

    def restore_editable_state(self) -> None:
        page = self.page
        self.apply_editable_info(page._last_editable_info)

    def sync_run_buttons_enabled(self) -> None:
        page = self.page
        enabled = not page._run_locked
        for btn in page._run_buttons:
            btn.setEnabled(enabled)

    def lock_for_running(self, locked: bool) -> None:
        from src.ui.view.config.actions import apply_run_lock_ui_state  # local import

        page = self.page
        page._run_locked = bool(locked)
        apply_run_lock_ui_state(page, locked)
        self.sync_run_buttons_enabled()


class ConfigController(
    _ConnectTypeControllerMixin,
    _StabilityControllerMixin,
    _CsvRvrControllerMixin,
    _RouterControllerMixin,
    _EditableStateControllerMixin,
):
    """
    Controller responsible for configuration lifecycle and normalisation
    for the Config page.

    This keeps all config I/O and structural cleanup out of the Qt widget
    class so that CaseConfigPage can focus on wiring UI and delegating
    business logic.
    """

    UI_EVENT_HANDLERS: Mapping[str, str] = {
        "field.change": "_on_field_change",
        "case.select": "_on_case_select",
        "csv.select": "_on_csv_select",
        "tab.switch": "_on_tab_switch",
        "action.run": "_on_action_run",
        "connect_type.changed": "_on_connect_type_changed",
        "connect_type.third_party": "_on_third_party_toggled",
        "serial.status.changed": "_on_serial_status_changed",
        "rf_model.changed": "_on_rf_model_changed",
        "rvr_tool.changed": "_on_rvr_tool_changed",
        "router.name.changed": "_on_router_name_changed",
        "router.address.changed": "_on_router_address_changed",
        "stability.exitfirst": "_on_stability_flags_changed",
        "stability.ping": "_on_stability_flags_changed",
        "stability.script_section": "_on_stability_flags_changed",
        "stability.relay_type": "_on_stability_flags_changed",
        "switch_wifi.use_router": "_on_switch_wifi_use_router",
        "switch_wifi.router_csv": "_on_switch_wifi_router_csv",
    }

    def __init__(self, page: "CaseConfigPage") -> None:
        self.page = page

    def get_application_base(self) -> Path:
        """Return the application source base path (was CaseConfigPage._get_application_base)."""
        return Path(get_src_base()).resolve()

    def init_case_tree(self, root_dir: Path) -> None:
        """Initialize the case tree model + proxy rooted at ``root_dir``."""
        from PyQt5.QtWidgets import QFileSystemModel
        from PyQt5.QtCore import QDir

        page = self.page
        page.fs_model = QFileSystemModel(page.case_tree)
        root_index = page.fs_model.setRootPath(str(root_dir))
        page.fs_model.setNameFilters(["test_*.py"])
        page.fs_model.setNameFilterDisables(True)
        page.fs_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Files)

        page.proxy_model = TestFileFilterModel()
        page.proxy_model.setSourceModel(page.fs_model)
        page.case_tree.setModel(page.proxy_model)
        page.case_tree.setRootIndex(page.proxy_model.mapFromSource(root_index))

        page.case_tree.header().hide()
        for col in range(1, page.fs_model.columnCount()):
            page.case_tree.hideColumn(col)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load_initial_config(self) -> dict:
        """
        Load configuration data from disk and normalise persisted paths.

        - Populates page.config
        - Captures the TOOL_SECTION snapshot for change detection
        - Restores CSV selection into page.selected_csv_path if supported
        """
        page = self.page
        page.config = load_config_page_state(page)
        return page.config

    def save_config(self) -> None:
        """Persist the active configuration and refresh cached state."""
        page = self.page
        page.config = save_config_page_state(page)

    # ------------------------------------------------------------------
    # Stability case defaults
    # ------------------------------------------------------------------

      # ------------------------------------------------------------------
      # Unified UI event entrypoint
      # ------------------------------------------------------------------

    def handle_ui_event(self, event: UiEvent) -> None:
        """Dispatch a UiEvent emitted by the adapter to a dedicated handler.

        This method is the single entrypoint for all user-driven Config UI
        interactions once the UiAdapter layer is in place.  Legacy callers
        using ``handle_config_event`` can be gradually migrated to emit
        :class:`UiEvent` instances instead of calling controller helpers
        directly.
        """
        handlers = {
            "field.change": self._on_field_change,
            "case.select": self._on_case_select,
            "csv.select": self._on_csv_select,
            "tab.switch": self._on_tab_switch,
            "action.run": self._on_action_run,
            "connect_type.changed": self._on_connect_type_changed,
            "connect_type.third_party": self._on_third_party_toggled,
            "serial.status.changed": self._on_serial_status_changed,
            "rf_model.changed": self._on_rf_model_changed,
            "rvr_tool.changed": self._on_rvr_tool_changed,
            "router.name.changed": self._on_router_name_changed,
            "router.address.changed": self._on_router_address_changed,
            "stability.exitfirst": self._on_stability_flags_changed,
            "stability.ping": self._on_stability_flags_changed,
            "stability.script_section": self._on_stability_flags_changed,
            "stability.relay_type": self._on_stability_flags_changed,
            "switch_wifi.use_router": self._on_switch_wifi_use_router,
            "switch_wifi.router_csv": self._on_switch_wifi_router_csv,
        }
        handler = handlers.get(event.kind)
        if handler is not None:
            handler(event)

    # Individual handlers are intentionally thin wrappers around existing
    # helpers so that behaviour can be verified incrementally.  After the
    # Phase 2 refactor, they host all controller-side business logic and no
    # longer delegate back to ``handle_config_event``.

    def _on_field_change(self, event: UiEvent) -> None:
        """Handle generic field-change events from the UI."""
        from PyQt5.QtCore import QTimer  # local import
        from src.ui.view.config.actions import _refresh_case_page_compatibility  # type: ignore[attr-defined]
        from src.ui.model.autosave import should_autosave

        page = self.page
        field = str(event.payload["field"]).strip()

        if field.startswith("compatibility."):
            QTimer.singleShot(0, lambda: _refresh_case_page_compatibility(page))

        if field != "csv_path" and should_autosave("field_changed") and not page._refreshing:
            self.sync_widgets_to_config()
            self.save_config()

        trigger = field or None
        evaluate_all_rules(page, trigger)

    def _on_case_select(self, event: UiEvent) -> None:
        """Handle case selection from the tree view."""
        page = self.page
        case_path = str(event.payload["case_path"])
        display_path = str(event.payload["display_path"])

        page._current_case_path = case_path
        page._current_case_display_path = display_path

        # Update "Selected Test Case" text if such a field exists.
        updated_widgets: set[int] = set()
        text_value = display_path or case_path
        for key, widget in page.field_widgets.items():
            if key == "text_case" or key.endswith(".text_case"):
                if id(widget) in updated_widgets:
                    continue
                widget.setText(text_value)
                updated_widgets.add(id(widget))

        # Re-compute testcase-specific UI and apply rules.
        from src.ui.view.config.actions import apply_ui  # local import

        apply_ui(page, case_path)

        if self.is_stability_case(case_path):
            page.view.set_current_page("stability")
        elif self.is_performance_case(case_path):
            page.view.set_current_page("execution")

    def _on_csv_select(self, event: UiEvent) -> None:
        """Handle main CSV combo selection changes."""
        page = self.page
        index = int(event.payload["index"])
        force = bool(event.payload["force"])

        csv_combo = page.csv_combo
        if index < 0:
            self.set_selected_csv(None, sync_combo=False)
            return
        data = csv_combo.itemData(index)
        new_path = self.normalize_csv_path(data)
        current = page.selected_csv_path
        if not force and new_path == current:
            return
        self.set_selected_csv(new_path, sync_combo=False)
        page.selected_csv_path = new_path

        page.csvFileChanged.emit(new_path or "")

        from src.ui.view.config.config_switch_wifi import sync_switch_wifi_on_csv_changed  # local import
        from src.ui.model.autosave import should_autosave  # local import

        sync_switch_wifi_on_csv_changed(page, new_path)

        if not page._refreshing and should_autosave("csv_index_changed"):
            self.sync_widgets_to_config()
            self.save_config()

    def _on_tab_switch(self, event: UiEvent) -> None:
        """Handle Config tab switches."""
        key = str(event.payload["key"]).strip()
        self.page.view.set_current_page(key)

    def _on_connect_type_changed(self, event: UiEvent) -> None:
        """Handle Control Type combo changes."""
        from src.ui.view.config.actions import handle_connect_type_changed

        text = event.payload["text"]
        handle_connect_type_changed(self.page, text)

    def _on_third_party_toggled(self, event: UiEvent) -> None:
        """Handle Third-party checkbox toggles."""
        from src.ui.view.config.actions import handle_third_party_toggled

        checked = bool(event.payload["checked"])
        handle_third_party_toggled(self.page, checked)

    def _on_serial_status_changed(self, event: UiEvent) -> None:
        """Handle Serial status checkbox changes."""
        from src.ui.view.config.actions import apply_serial_enabled_ui_state, _rebalance_panel

        text = str(event.payload["text"])
        page = self.page
        apply_serial_enabled_ui_state(page, text)
        _rebalance_panel(page._dut_panel)

    def _on_rf_model_changed(self, event: UiEvent) -> None:
        """Handle RF model combo changes (panel rebalance only)."""
        from src.ui.view.config.actions import _rebalance_panel

        _rebalance_panel(self.page._execution_panel)

    def _on_rvr_tool_changed(self, event: UiEvent) -> None:
        """Handle RvR tool selection changes."""
        from src.ui.view.config.actions import apply_rvr_tool_ui_state, _rebalance_panel

        tool_text = str(event.payload["tool_text"])
        page = self.page
        apply_rvr_tool_ui_state(page, tool_text)
        _rebalance_panel(page._execution_panel)

    def _on_router_name_changed(self, event: UiEvent) -> None:
        """Handle router name edits."""
        name = str(event.payload["name"])
        self.handle_router_name_changed(name)

    def _on_router_address_changed(self, event: UiEvent) -> None:
        """Handle router address edits."""
        address = str(event.payload["address"])
        self.handle_router_address_changed(address)

    def _on_stability_flags_changed(self, event: UiEvent) -> None:
        """Re-evaluate rules after stability-related toggles."""
        _ = event
        evaluate_all_rules(self.page, None)

    def _on_switch_wifi_use_router(self, event: UiEvent) -> None:
        """Handle switch_wifi use-router toggles (stability section)."""
        from src.ui.view.config.config_switch_wifi import handle_switch_wifi_use_router_changed

        page = self.page
        checked = bool(event.payload["checked"])
        handle_switch_wifi_use_router_changed(page, checked)
        self._on_stability_flags_changed(event)

    def _on_switch_wifi_router_csv(self, event: UiEvent) -> None:
        """Handle switch_wifi router-CSV combo changes (stability section)."""
        from src.ui.view.config.config_switch_wifi import handle_switch_wifi_router_csv_changed

        page = self.page
        index = int(event.payload["index"])
        handle_switch_wifi_router_csv_changed(page, index)
        self._on_stability_flags_changed(event)

    def _on_action_run(self, event: UiEvent) -> None:
        _ = event
        self.on_run()  # type: ignore[call-arg]

    # ------------------------------------------------------------------
    # FPGA helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_fpga_token(value: Any) -> str:
        """Coerce FPGA metadata tokens into normalised uppercase strings."""
        if value is None:
            return ""
        return str(value).strip().upper()

    @staticmethod
    def _split_legacy_fpga_value(raw: str) -> tuple[str, str]:
        """Split legacy `wifi_module_interface` values for compatibility."""
        parts = raw.split("_", 1)
        wifi_module = parts[0] if parts and parts[0] else ""
        interface = parts[1] if len(parts) > 1 and parts[1] else ""
        return wifi_module.upper(), interface.upper()

    def _find_project_in_map(
        self,
        wifi_module: str,
        interface: str,
        main_chip: str = "",
        *,
        customer: str = "",
        product_line: str = "",
        project: str = "",
    ) -> tuple[str, str, str, Optional[dict[str, str]]]:
        """Resolve project metadata from WIFI_PRODUCT_PROJECT_MAP."""
        wifi_upper = wifi_module.strip().upper()
        interface_upper = interface.strip().upper()
        chip_upper = main_chip.strip().upper()
        customer_upper = customer.strip().upper()
        product_upper = product_line.strip().upper()
        project_upper = project.strip().upper()
        for customer_name, product_lines in WIFI_PRODUCT_PROJECT_MAP.items():
            customer_name_upper = self.normalize_fpga_token(customer_name)
            if customer_upper and customer_name_upper != customer_upper:
                continue
            for product_name, projects in product_lines.items():
                product_name_upper = self.normalize_fpga_token(product_name)
                if product_upper and product_name_upper != product_upper:
                    continue
                for project_name, info in projects.items():
                    project_name_upper = self.normalize_fpga_token(project_name)
                    if project_upper and project_name_upper != project_upper:
                        continue
                    info_wifi = self.normalize_fpga_token(info.get("wifi_module"))
                    info_if = self.normalize_fpga_token(info.get("interface"))
                    info_chip = self.normalize_fpga_token(info.get("main_chip"))
                    if wifi_upper and info_wifi and info_wifi != wifi_upper:
                        continue
                    if interface_upper and info_if and info_if != interface_upper:
                        continue
                    if chip_upper and info_chip and info_chip != chip_upper:
                        continue
                    return customer_name, product_name, project_name, info
        return "", "", "", None

    def normalize_project_section(self, raw_value: Any) -> dict[str, str]:
        """Normalise project configuration into structured token fields.

        The persisted source of truth is the (customer, product_line,
        project) triple chosen by the user.  ``wifi_module``,
        ``interface`` and ``main_chip`` are derived from
        :data:`WIFI_PRODUCT_PROJECT_MAP` when a matching entry exists.
        """
        normalized = {
            "customer": "",
            "product_line": "",
            "project": "",
            "main_chip": "",
            "wifi_module": "",
            "interface": "",
        }
        if isinstance(raw_value, Mapping):
            customer = self.normalize_fpga_token(raw_value.get("customer"))
            product_line = self.normalize_fpga_token(raw_value.get("product_line"))
            project = self.normalize_fpga_token(raw_value.get("project"))
            normalized.update(
                {
                    "customer": customer,
                    "product_line": product_line,
                    "project": project,
                }
            )
            # Derive details from the project triple when possible; do not
            # overwrite the triple itself so YAML remains the source of truth.
            _, _, _, info = self._find_project_in_map(
                "",
                "",
                "",
                customer=customer,
                product_line=product_line,
                project=project,
            )
            if info:
                normalized["main_chip"] = self.normalize_fpga_token(info.get("main_chip"))
                normalized["wifi_module"] = self.normalize_fpga_token(info.get("wifi_module"))
                normalized["interface"] = self.normalize_fpga_token(info.get("interface"))
        elif isinstance(raw_value, str):
            # Legacy string format: attempt to resolve project triple from
            # encoded wifi_module/interface and derive details accordingly.
            wifi_module, interface = self._split_legacy_fpga_value(raw_value)
            customer, product, project, info = self._find_project_in_map(
                wifi_module,
                interface,
            )
            if customer:
                normalized["customer"] = customer
            if product:
                normalized["product_line"] = product
            if project:
                normalized["project"] = project
            if info:
                normalized["main_chip"] = self.normalize_fpga_token(info.get("main_chip"))
                normalized["wifi_module"] = self.normalize_fpga_token(info.get("wifi_module"))
                normalized["interface"] = self.normalize_fpga_token(info.get("interface"))
        return normalized

    # ------------------------------------------------------------------
    # Connect-type / stability normalisation
    # ------------------------------------------------------------------

    def normalize_connect_type_section(self, raw_value: Any) -> dict[str, Any]:
        """Normalise connect-type data, supporting legacy adb/telnet fields."""
        normalized: dict[str, Any] = {}
        if isinstance(raw_value, Mapping):
            normalized.update(raw_value)

        type_value = normalized.get("type", "Android")
        if isinstance(type_value, str):
            type_value = type_value.strip() or "Android"
        else:
            type_value = str(type_value).strip() or "Android"
        lowered_type = type_value.lower()
        if lowered_type in {"android", "adb"}:
            type_value = "Android"
        elif lowered_type in {"linux", "telnet"}:
            type_value = "Linux"
        normalized["type"] = type_value

        android_cfg = normalized.get("Android")
        if not isinstance(android_cfg, Mapping):
            legacy_adb = normalized.get("adb")
            if isinstance(legacy_adb, Mapping):
                android_cfg = legacy_adb
            else:
                android_cfg = legacy_adb
        if isinstance(android_cfg, Mapping):
            android_dict = dict(android_cfg)
        else:
            android_dict = {}
            if android_cfg not in (None, ""):
                android_dict["device"] = str(android_cfg)
        device = android_dict.get("device", "")
        android_dict["device"] = str(device).strip() if device is not None else ""
        normalized["Android"] = android_dict
        normalized.pop("adb", None)

        linux_cfg = normalized.get("Linux")
        if not isinstance(linux_cfg, Mapping):
            legacy_telnet = normalized.get("telnet")
            if isinstance(legacy_telnet, Mapping):
                linux_cfg = legacy_telnet
            else:
                linux_cfg = legacy_telnet
        if isinstance(linux_cfg, Mapping):
            linux_dict = dict(linux_cfg)
        else:
            linux_dict = {}
            if isinstance(linux_cfg, str) and linux_cfg.strip():
                linux_dict["ip"] = linux_cfg.strip()
        telnet_ip = linux_dict.get("ip", "")
        linux_dict["ip"] = str(telnet_ip).strip() if telnet_ip is not None else ""
        wildcard = linux_dict.get("wildcard", "")
        linux_dict["wildcard"] = str(wildcard).strip() if wildcard is not None else ""
        normalized["Linux"] = linux_dict
        normalized.pop("telnet", None)

        third_cfg = normalized.get("third_party")
        if isinstance(third_cfg, Mapping):
            third_dict = dict(third_cfg)
        else:
            third_dict = {}
        enabled_val = third_dict.get("enabled", False)
        if isinstance(enabled_val, str):
            enabled_bool = enabled_val.strip().lower() in {"1", "true", "yes", "on"}
        else:
            enabled_bool = bool(enabled_val)
        third_dict["enabled"] = enabled_bool
        wait_val = third_dict.get("wait_seconds")
        wait_seconds_str = str(wait_val).strip() if wait_val not in (None, "") else ""
        wait_seconds = int(wait_seconds_str) if wait_seconds_str else None
        third_dict["wait_seconds"] = wait_seconds if wait_seconds is None or wait_seconds > 0 else None
        normalized["third_party"] = third_dict

        return normalized

    def normalize_stability_settings(self, raw_value: Any) -> dict[str, Any]:
        """Normalise stability settings including duration, checkpoints, cases."""

        def _normalize_cycle(value: Any) -> dict[str, Any]:
            mapping = value if isinstance(value, Mapping) else {}
            return {
                "enabled": bool(mapping.get("enabled")),
                "on_duration": max(0, int(mapping.get("on_duration", 0) or 0)),
                "off_duration": max(0, int(mapping.get("off_duration", 0) or 0)),
                "port": str(mapping.get("port", "") or "").strip(),
                "mode": str(mapping.get("mode", "") or "NO").strip().upper() or "NO",
            }

        source = raw_value if isinstance(raw_value, Mapping) else {}

        duration_cfg = source.get("duration_control", {})
        loop_str = str(duration_cfg.get("loop", "")).strip()
        loop_value = int(loop_str) if loop_str.isdigit() and int(loop_str) > 0 else None
        duration_str = str(duration_cfg.get("duration_hours", "")).strip()
        is_duration_number = duration_str.replace(".", "", 1).isdigit() if duration_str else False
        duration_value = float(duration_str) if is_duration_number and float(duration_str) > 0 else None
        exitfirst_flag = bool(duration_cfg.get("exitfirst"))
        retry_str = str(duration_cfg.get("retry_limit", "")).strip()
        retry_limit = int(retry_str) if retry_str.isdigit() and int(retry_str) > 0 else 0

        check_point_cfg = source.get("check_point", {})
        check_point = {key: bool(value) for key, value in check_point_cfg.items()}
        check_point.setdefault("ping", False)
        check_point["ping_targets"] = str(check_point_cfg.get("ping_targets", "")).strip()

        cases_cfg = source.get("cases", {})
        cases: dict[str, dict[str, Any]] = {}
        for name, case_value in cases_cfg.items():
            normalized_name = SWITCH_WIFI_CASE_KEY if name in SWITCH_WIFI_CASE_KEYS else name
            if normalized_name == SWITCH_WIFI_CASE_KEY:
                manual_entries = case_value.get(SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
                from src.ui.view.config.config_switch_wifi import normalize_switch_wifi_manual_entries

                cases[SWITCH_WIFI_CASE_KEY] = {
                    "ac": _normalize_cycle(case_value.get("ac")),
                    "str": _normalize_cycle(case_value.get("str")),
                    SWITCH_WIFI_USE_ROUTER_FIELD: bool(
                        case_value.get(SWITCH_WIFI_USE_ROUTER_FIELD)
                    ),
                    SWITCH_WIFI_ROUTER_CSV_FIELD: str(
                        case_value.get(SWITCH_WIFI_ROUTER_CSV_FIELD, "") or ""
                    ).strip(),
                    SWITCH_WIFI_MANUAL_ENTRIES_FIELD: normalize_switch_wifi_manual_entries(
                        manual_entries
                    ),
                }
            else:
                cases[normalized_name] = {
                    "ac": _normalize_cycle(case_value.get("ac")),
                    "str": _normalize_cycle(case_value.get("str")),
                }

        return {
            "duration_control": {
                "loop": loop_value,
                "duration_hours": duration_value,
                "exitfirst": exitfirst_flag,
                "retry_limit": retry_limit,
            },
            "check_point": check_point,
            "cases": cases,
        }

    # ------------------------------------------------------------------
    # Stability script config glue
    # ------------------------------------------------------------------

    def load_script_config_into_widgets(
        self,
        entry: ScriptConfigEntry,
        data: Mapping[str, Any] | None,
    ) -> None:
        """
        Load stability script config into widgets from persistent storage.

        Handles both ``test_switch_wifi`` (router/manual Wi-Fi list) and
        ``test_str`` AC/STR timing + relay controls.
        """
        # Delegate to the view-layer helper so the UI-side implementation
        # lives with other visual logic. Keep this thin wrapper to avoid
        # breaking callers that expect the controller API.
        from src.ui.view.config.actions import load_script_config_into_widgets as _view_load

        _view_load(self.page, entry, data)
        return

    def sync_widgets_to_config(self) -> None:
        """Read all widgets into page.config, including stability settings."""
        page = self.page
        page.config[TOOL_SECTION_KEY] = copy.deepcopy(page._config_tool_snapshot)
        for key, widget in page.field_widgets.items():
            parts = key.split(".")
            ref = page.config
            for part in parts[:-1]:
                child = ref.get(part)
                if not isinstance(child, dict):
                    child = {}
                    ref[part] = child
                ref = child
            leaf = parts[-1]
            if isinstance(widget, LineEdit):
                val = widget.text()
                if key == "connect_type.third_party.wait_seconds":
                    val = val.strip()
                    ref[leaf] = int(val) if val else 0
                    continue
                if key == "rf_solution.step":
                    ref[leaf] = val.strip()
                    continue
                if key == f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_STEP}":
                    ref[leaf] = val.strip()
                    continue
                if key == f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_STATIC_DB}":
                    ref[leaf] = val.strip()
                    continue
                if key == f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_TARGET_RSSI}":
                    ref[leaf] = val.strip()
                    continue
                if key == f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_IP_ADDRESS}":
                    ref[leaf] = val.strip()
                    continue
                if leaf == "relay_params":
                    items = [item.strip() for item in val.split(",") if item.strip()]
                    normalized = []
                    for item in items:
                        normalized.append(int(item) if item.isdigit() else item)
                    ref[leaf] = normalized
                    continue
                old_val = ref.get(leaf)
                if isinstance(old_val, list):
                    items = [x.strip() for x in val.split(",") if x.strip()]
                    if all(i.isdigit() for i in items):
                        ref[leaf] = [int(i) for i in items]
                    else:
                        ref[leaf] = items
                else:
                    val = val.strip()
                    if len(parts) >= 2 and parts[-2] == "router" and leaf.startswith("passwd") and not val:
                        ref[leaf] = ""
                    else:
                        ref[leaf] = val
            elif isinstance(widget, RfStepSegmentsWidget):
                ref[leaf] = widget.serialize()
            elif isinstance(widget, SwitchWifiConfigPage):
                # Persist manual_entries for ``test_switch_wifi`` when the
                # testcase is in manual mode. When the user enables router
                # configuration (``use_router=True``), the list editor shows
                # a CSV preview that must *not* be written back into the
                # stability YAML; in that mode we skip serialization here.
                from src.ui.view.config import script_field_key as _script_key
                from src.util.constants import (
                    SWITCH_WIFI_CASE_KEY as _SW_CASE,
                    SWITCH_WIFI_USE_ROUTER_FIELD as _SW_USE_ROUTER,
                )

                use_router_widget = page.field_widgets.get(
                    _script_key(_SW_CASE, _SW_USE_ROUTER)
                )
                is_router_mode = isinstance(use_router_widget, QCheckBox) and use_router_widget.isChecked()
                if is_router_mode:
                    continue
                ref[leaf] = widget.serialize()
            elif isinstance(widget, CompatibilityRelayEditor):
                # Persist compatibility.power_ctrl.relays from the composite
                # editor used on the Compatibility Settings panel.
                relays = widget.relays()
                ref[leaf] = relays
                # Keep compatibility section free of redundant selected_routers.
                compat_cfg = page.config.setdefault("compatibility", {})
                compat_cfg.pop("selected_routers", None)
            elif isinstance(widget, ComboBox):
                data_val = widget.currentData()
                if data_val not in (None, "", widget.currentText()):
                    value = data_val
                else:
                    text = widget.currentText().strip()
                    if text.lower() == "select port":
                        text = ""
                    value = True if text == "True" else False if text == "False" else text
                if key == script_field_key(
                    SWITCH_WIFI_CASE_KEY, SWITCH_WIFI_ROUTER_CSV_FIELD
                ):
                    value = self.relativize_config_path(value)
                ref[leaf] = value
            elif isinstance(widget, QSpinBox):
                ref[leaf] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                ref[leaf] = float(widget.value())
            elif isinstance(widget, QCheckBox):
                ref[leaf] = widget.isChecked()
        page.config["project"] = dict(page._fpga_details)
        base = Path(self.get_application_base())
        case_display = page.field_widgets.get("text_case")
        display_text = case_display.text().strip() if isinstance(case_display, LineEdit) else ""
        storage_path = page._current_case_path or display_to_case_path(display_text)
        case_path = Path(storage_path).as_posix() if storage_path else ""
        page._current_case_path = case_path
        if case_path:
            abs_case_path = (base / case_path).resolve().as_posix()
        else:
            abs_case_path = ""
        page.config["text_case"] = case_path
        base_cfg = get_config_base()
        csv_path = page.selected_csv_path
        if csv_path:
            rel_csv = os.path.relpath(Path(csv_path).resolve(), base_cfg)
            page.config["csv_path"] = Path(rel_csv).as_posix()
        else:
            page.config["csv_path"] = ""
        proxy_idx = page.case_tree.currentIndex()
        model = page.case_tree.model()
        src_idx = (
            model.mapToSource(proxy_idx)
            if isinstance(model, QSortFilterProxyModel)
            else proxy_idx
        )
        selected_path = page.fs_model.filePath(src_idx)
        if os.path.isfile(selected_path) and selected_path.endswith(".py"):
            abs_path = Path(selected_path).resolve()
            display_path = os.path.relpath(abs_path, base)
            case_path = Path(display_path).as_posix()
            page._current_case_path = case_path
            page.config["text_case"] = case_path

        stability_cfg = self.normalize_stability_settings(page.config.get("stability", {}))
        page.config["stability"] = stability_cfg

    def validate_test_str_requirements(self) -> bool:
        """Ensure test_str stability settings require port/mode when AC/STR enabled."""
        page = self.page
        config = page.config
        case_path = config.get("text_case", "")
        case_key = self.script_case_key(case_path)
        if case_key != "test_str":
            return True

        stability_cfg = config.get("stability", {})
        cases_cfg = stability_cfg.get("cases", {})
        case_cfg = cases_cfg.get(case_key, {})

        errors: list[str] = []
        focus_widget = None

        def _require(branch: str, label: str) -> None:
            nonlocal focus_widget
            branch_cfg = case_cfg.get(branch, {})
            if not branch_cfg.get("enabled"):
                return
            relay_type = str(branch_cfg.get("relay_type") or "usb_relay").strip() or "usb_relay"
            relay_key = relay_type.lower()
            if relay_key == "usb_relay":
                port_value = str(branch_cfg.get("port") or "").strip()
                mode_value = str(branch_cfg.get("mode") or "").strip()
                if not port_value:
                    errors.append(f"{label}: USB power relay port is required.")
                    focus_widget = focus_widget or page.field_widgets.get(
                        f"stability.cases.{case_key}.{branch}.port"
                    )
                if not mode_value:
                    errors.append(f"{label}: Wiring mode is required.")
                    focus_widget = focus_widget or page.field_widgets.get(
                        f"stability.cases.{case_key}.{branch}.mode"
                    )
            elif relay_key == "gwgj-xc3012":
                params = branch_cfg.get("relay_params", [])
                items = (
                    list(params)
                    if isinstance(params, (list, tuple))
                    else [item.strip() for item in str(params).split(",") if item.strip()]
                )
                ip_value = str(items[0]).strip() if items else ""
                port_value = None
                if len(items) > 1:
                    port_value = int(str(items[1]).strip())
                if not ip_value or port_value is None:
                    errors.append(
                        f"{label}: Relay params must include IP and port for GWGJ-XC3012."
                    )
                    focus_widget = focus_widget or page.field_widgets.get(
                        f"stability.cases.{case_key}.{branch}.relay_params"
                    )

        _require("ac", "AC cycle")
        _require("str", "STR cycle")
        if not errors:
            return True

        message = "\n".join(errors)
        bar = show_info_bar(
            page,
            "warning",
            "Configuration error",
            message,
            duration=4000,
        )
        if bar is None:
            from PyQt5.QtWidgets import QMessageBox  # local import

            QMessageBox.warning(page, "Configuration error", message)
        if focus_widget is not None:
            focus_widget.setFocus()
            focus_widget.selectAll()
        return False

    def validate_first_page(self) -> bool:
        """Validate DUT page before running or navigating to subsequent pages."""
        from src.ui.view.config.actions import current_connect_type  # local import

        page = self.page
        errors: list[str] = []
        connect_type = ""
        focus_widget = None
        widgets = page.field_widgets
        connect_type = current_connect_type(page)
        if not connect_type:
            errors.append("Connect type is required.")
            focus_widget = focus_widget or page.connect_type_combo
        elif connect_type == "Android":
            android_device_edit = widgets["connect_type.Android.device"]
            if not android_device_edit.text().strip():
                errors.append("ADB device is required.")
                focus_widget = focus_widget or android_device_edit
        elif connect_type == "Linux":
            telnet_ip_edit = widgets["connect_type.Linux.ip"]
            if not telnet_ip_edit.text().strip():
                errors.append("Linux IP is required.")
                focus_widget = focus_widget or telnet_ip_edit
            kernel_text = page.kernel_version_combo.currentText().strip()
            if not kernel_text:
                errors.append("Kernel version is required for Linux access.")
                focus_widget = focus_widget or page.kernel_version_combo
        if page.third_party_checkbox.isChecked():
            wait_text = page.third_party_wait_edit.text().strip()
            if not wait_text or not wait_text.isdigit() or int(wait_text) <= 0:
                errors.append("Third-party wait time must be a positive integer.")
                focus_widget = focus_widget or page.third_party_wait_edit

        if connect_type == "Android" and not page.android_version_combo.currentText().strip():
            errors.append("Android version is required.")
            focus_widget = focus_widget or page.android_version_combo

        customer_text = page.fpga_customer_combo.currentText().strip()
        product_text = page.fpga_product_combo.currentText().strip()
        project_text = page.fpga_project_combo.currentText().strip()
        if not customer_text or not product_text or not project_text:
            errors.append(
                "Wi-Fi chipset customer, product line and project are required."
            )
            focus_widget = focus_widget or (
                page.fpga_customer_combo
                if not customer_text
                else page.fpga_product_combo
                if not product_text
                else page.fpga_project_combo
            )

        if errors:
            show_info_bar(
                page,
                "warning",
                "Validation",
                "\n".join(errors),
                duration=3000,
            )
            if focus_widget is not None:
                focus_widget.setFocus()
                focus_widget.selectAll()
            return False
        return True

    # ------------------------------------------------------------------
    # Case classification / page selection
    # ------------------------------------------------------------------

    def is_performance_case(self, abs_case_path: str | Path | None) -> bool:
        if not abs_case_path:
            return False
        p = Path(abs_case_path).resolve()
        for node in (p, *p.parents):
            if node.name == "performance" and node.parent.name == "test":
                return True
        return False

    def is_stability_case(self, case_path: str | Path | None) -> bool:
        """Return True when the case resides under ``test/stability``."""

        if not case_path:
            return False
        path_obj = case_path if isinstance(case_path, Path) else Path(case_path)
        resolved = path_obj.resolve()
        segments = [seg.lower() for seg in resolved.as_posix().split("/") if seg]
        for idx in range(len(segments) - 1):
            if segments[idx] == "test" and segments[idx + 1] == "stability":
                return True
        return False

    def script_case_key(self, case_path: str | Path) -> str:
        """Return the logical script key used by stability config for the given case path."""
        if not case_path:
            return ""
        path_obj = case_path if isinstance(case_path, Path) else Path(case_path)
        if path_obj.is_absolute():
            from src.util.constants import get_src_base

            path_obj = path_obj.resolve().relative_to(Path(get_src_base()).resolve())
        stem = path_obj.stem.lower()
        if stem in SWITCH_WIFI_CASE_KEYS:
            return SWITCH_WIFI_CASE_KEY
        return stem

    def determine_pages_for_case(self, case_path: str, info: "EditableInfo") -> list[str]:
        """Return which logical pages (basic/execution/stability/compatibility) are visible for the case."""
        if not case_path:
            return ["basic"]

        keys = ["basic"]

        # Derive category primarily from the folder under ``test`` so that
        # Settings tabs map to top-level test directories.
        from src.ui.view import determine_case_category  # local import to avoid cycles

        category = determine_case_category(case_path=case_path, display_path=None)

        if category == "compatibility":
            if "compatibility" not in keys:
                keys.append("compatibility")
            return keys

        if self.is_performance_case(case_path) or info.enable_csv:
            if "execution" not in keys:
                keys.append("execution")
        else:
            case_key = self.script_case_key(case_path)
            script_groups = self.page._script_groups
            if case_key in script_groups:
                keys.append("stability")
        return keys

    # ------------------------------------------------------------------
    # Editable state / rules bridge
    # ------------------------------------------------------------------

    def get_field_value(self, field_key: str) -> Any:
        """Return a Python value representing the current state of a field widget."""
        page = self.page
        widget = page.field_widgets.get(field_key)
        if widget is None:
            return None
        from qfluentwidgets import ComboBox, LineEdit, TextEdit  # local import

        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, ComboBox):
            data = widget.currentData()
            if data not in (None, ""):
                return data
            return widget.currentText()
        if isinstance(widget, LineEdit):
            return widget.text()
        if isinstance(widget, TextEdit):
            return widget.toPlainText()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QDoubleSpinBox):
            return float(widget.value())
        return None

    def eval_case_type_flag(self, flag: str) -> bool:
        """Return True/False for high level case-type flags used by rules."""
        page = self.page
        if not flag:
            return True
        case_path = page._current_case_path
        basename = os.path.basename(case_path) if case_path else ""
        abs_path = case_path
        path_obj = Path(case_path)
        abs_path = (
            (Path(self.get_application_base()) / path_obj).as_posix()
            if not path_obj.is_absolute()
            else path_obj.as_posix()
        )
        if flag == "performance_or_enable_csv":
            info = page._last_editable_info
            return bool(self.is_performance_case(abs_path) or info.enable_csv)
        if flag == "execution_panel_visible":
            return "execution" in page._current_page_keys
        if flag == "stability_case":
            return self.is_stability_case(abs_path or case_path)
        if flag == "rvr_case":
            return "rvr" in basename.lower()
        if flag == "rvo_case":
            return "rvo" in basename.lower()
        if flag == "performance_case_with_rvr_wifi":
              return bool(self.is_performance_case(abs_path) and page._enable_rvr_wifi and page.selected_csv_path)
        return False

    def apply_sidebar_rules(self) -> None:
        """Evaluate sidebar rules that depend on the active case."""
        from src.ui.model.rules import SIDEBAR_RULES, RuleSpec  # local import

        page = self.page
        main_window = page.window()
        rules: dict[str, RuleSpec] = SIDEBAR_RULES

        spec = rules["S11_case_button_for_performance"]
        sidebar_key = spec.get("trigger_sidebar_key") or "case"
        sidebar_enabled = self.eval_case_type_flag(
            spec.get("trigger_case_type") or ""
        )

        sidebar_map = main_window.sidebar_nav_buttons
        btn = sidebar_map.get(sidebar_key) or main_window.rvr_nav_button
        btn.setEnabled(bool(sidebar_enabled))

    def apply_editable_info(self, info: "EditableInfo | None") -> None:
        """Apply EditableInfo to model flags and non-rule UI.

        This helper updates internal flags (CSV / RvR Wi-Fi) and basic UI
        such as CSV combo enabled state.  Field-level enabled/visible state
        is controlled exclusively by the simple rule engine so this method
        no longer calls ``set_fields_editable``.
        """
        page = self.page
        if info is None:
            fields: set[str] = set()
            enable_csv = False
            enable_rvr_wifi = False
        else:
            fields = set(info.fields)
            enable_csv = info.enable_csv
            enable_rvr_wifi = info.enable_rvr_wifi
        snapshot = EditableInfo(
            fields=fields,
            enable_csv=enable_csv,
            enable_rvr_wifi=enable_rvr_wifi,
        )
        page._last_editable_info = snapshot
        self._apply_editable_model_state(snapshot)
        self._apply_editable_ui_state(snapshot)

    def _apply_editable_model_state(self, snapshot: "EditableInfo") -> None:
        """Update internal flags and CSV selection from EditableInfo (no direct UI)."""
        page = self.page
        page._enable_rvr_wifi = snapshot.enable_rvr_wifi
        if not snapshot.enable_rvr_wifi:
            page._router_config_active = False
        if snapshot.enable_csv:
            # Ensure selected CSV is applied and combo synced when CSV is enabled.
            self.set_selected_csv(page.selected_csv_path, sync_combo=True)
        else:
            # Clear CSV selection when CSV usage is disabled.
            self.set_selected_csv(None, sync_combo=False)

    def _apply_editable_ui_state(self, snapshot: "EditableInfo") -> None:
        """Apply UI-related changes for EditableInfo (non field-level widgets)."""
        page = self.page
        page.csv_combo.setEnabled(True)
        # Keep the RvR navigation button state in sync with CSV/router
        # configuration, but do not disable the Case button for
        # non‑performance cases – the Case page itself decides what
        # content to show for the active testcase.
        self.update_rvr_nav_button()

        # Drive the Case page content from the current EditableInfo:
        # when RvR Wi‑Fi is enabled for the selected testcase, show the
        # RvrWifiConfigPage UI; otherwise keep the Case page empty.
        main_window = page.window()
        rvr_page = main_window.rvr_wifi_config_page
        rvr_page.set_case_content_visible(bool(snapshot.enable_rvr_wifi))

    def restore_editable_state(self) -> None:
        """Re-apply last EditableInfo snapshot."""
        page = self.page
        self.apply_editable_info(page._last_editable_info)

    def on_run(self) -> None:
        """Main entry for running the currently selected case from the Config page."""
        from PyQt5.QtWidgets import QMessageBox  # local import

        page = self.page
        if not self.validate_first_page():
            page.stack.setCurrentIndex(0)
            return

        # Reload config to latest on-disk state, then sync widgets -> config.
        page.config = self.load_initial_config()
        self.capture_preselected_csv()
        self.sync_widgets_to_config()
        if not self.validate_test_str_requirements():
            return

        base = Path(self.get_application_base())
        case_path = page.config.get("text_case", "")
        abs_case_path = (base / case_path).resolve().as_posix() if case_path else ""

        proxy_idx = page.case_tree.currentIndex()
        model = page.case_tree.model()
        src_idx = (
            model.mapToSource(proxy_idx)
            if isinstance(model, QSortFilterProxyModel)
            else proxy_idx
        )
        selected_path = page.fs_model.filePath(src_idx)
        if os.path.isfile(selected_path) and selected_path.endswith(".py"):
            abs_path = Path(selected_path).resolve()
            display_path = os.path.relpath(abs_path, base)
            case_path = Path(display_path).as_posix()
            abs_case_path = abs_path.as_posix()
            page.config["text_case"] = case_path

        # Persist config before running.
        self.save_config()

        # Performance case must have CSV selected.
        if self.is_performance_case(abs_case_path) and not page.selected_csv_path:
            bar = show_info_bar(
                page,
                "warning",
                "Hint",
                "This is a performance test. Please select a CSV file before running.",
                duration=3000,
            )
            if bar is None:
                QMessageBox.warning(
                    page,
                    "Hint",
                    "This is a performance test.\nPlease select a CSV file before running.",
                )
            return

        from src.ui.controller.run_ctl import reset_wizard_after_run

        if os.path.isfile(abs_case_path) and abs_case_path.endswith(".py"):
            page.on_run_callback(abs_case_path, case_path, page.config)
            reset_wizard_after_run(page)
        else:
            show_info_bar(
                page,
                "warning",
                "Hint",
                "Pls select a test case before test",
                duration=1800,
            )



__all__ = ["ConfigController"]
