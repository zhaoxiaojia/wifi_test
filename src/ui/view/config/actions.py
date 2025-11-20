"""UI action helpers for the Config page.

These functions live in the *view* layer and encapsulate pure UI behaviour
for CaseConfigPage and ConfigView (show/hide groups, enable/disable fields,
update step indicators, etc.).  Controllers should delegate visual tweaks
to these helpers instead of hard-coding widget manipulation.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Sequence

from PyQt5.QtCore import QSortFilterProxyModel, QSignalBlocker
from PyQt5.QtWidgets import QWidget, QCheckBox, QFormLayout, QLabel

from src.util.constants import (
    TURN_TABLE_MODEL_OTHER,
    WIFI_PRODUCT_PROJECT_MAP,
    ANDROID_KERNEL_MAP,
)
from src.ui.model.rules import FieldEffect, RuleSpec, CONFIG_UI_RULES
from src.ui.view.builder import build_groups_from_schema, load_ui_schema
from src.ui.view.common import EditableInfo
from src.ui.view.config.config_switch_wifi import (
    sync_switch_wifi_on_csv_changed,
    handle_switch_wifi_use_router_changed,
    handle_switch_wifi_router_csv_changed,
    init_switch_wifi_actions,
)
from src import display_to_case_path, case_path_to_display, update_test_case_display


# --- Connect-type / Android system helpers (migrated from CaseConfigPage) ---
def normalize_connect_type_label(label: str) -> str:
    text = (label or "").strip()
    lowered = text.lower()
    if lowered in {"android", "adb"}:
        return "Android"
    if lowered in {"linux", "telnet"}:
        return "Linux"
    return text


def current_connect_type(page: Any) -> str:
    """Return the canonical connect type for the given page (best-effort)."""
    try:
        # Prefer an existing page-provided helper for backward-compat.
        if hasattr(page, "_current_connect_type"):
            return page._current_connect_type() or ""
        if not hasattr(page, "connect_type_combo"):
            return ""
        data = page.connect_type_combo.currentData()
        if isinstance(data, str) and data.strip():
            return data.strip()
        text = page.connect_type_combo.currentText()
        return normalize_connect_type_label(text) if isinstance(text, str) else ""
    except Exception:
        return ""


def set_connect_type_combo_selection(page: Any, type_value: str) -> None:
    if not hasattr(page, "connect_type_combo"):
        return
    target_value = normalize_connect_type_label(type_value)
    try:
        with QSignalBlocker(page.connect_type_combo):
            index = page.connect_type_combo.findData(target_value)
            if index >= 0:
                page.connect_type_combo.setCurrentIndex(index)
            elif page.connect_type_combo.count():
                page.connect_type_combo.setCurrentIndex(0)
    except Exception:
        logging.debug("set_connect_type_combo_selection failed", exc_info=True)


def _ensure_kernel_option(page: Any, kernel: str) -> None:
    if not kernel or not hasattr(page, "kernel_version_combo"):
        return
    try:
        combo = page.kernel_version_combo
        existing = {combo.itemText(i) for i in range(combo.count())}
        if kernel not in existing:
            combo.addItem(kernel)
        if not hasattr(page, "_kernel_versions"):
            try:
                page._kernel_versions = []
            except Exception:
                page._kernel_versions = []
        if kernel not in page._kernel_versions:
            page._kernel_versions.append(kernel)
    except Exception:
        logging.debug("_ensure_kernel_option failed", exc_info=True)


def apply_android_kernel_mapping(page: Any) -> None:
    if not hasattr(page, "android_version_combo") or not hasattr(page, "kernel_version_combo"):
        return
    try:
        version = page.android_version_combo.currentText().strip()
        kernel = ANDROID_KERNEL_MAP.get(version, "")
        if kernel:
            _ensure_kernel_option(page, kernel)
            page.kernel_version_combo.setCurrentText(kernel)
        else:
            page.kernel_version_combo.setCurrentIndex(-1)
    except Exception:
        logging.debug("apply_android_kernel_mapping failed", exc_info=True)


def update_android_system_for_connect_type(page: Any, connect_type: str) -> None:
    if not hasattr(page, "android_version_combo") or not hasattr(page, "kernel_version_combo"):
        return
    try:
        is_adb = connect_type == "Android"
        if is_adb:
            apply_android_kernel_mapping(page)
        else:
            if not page.kernel_version_combo.currentText().strip():
                page.kernel_version_combo.setCurrentIndex(-1)
    except Exception:
        logging.debug("update_android_system_for_connect_type failed", exc_info=True)


def on_android_version_changed(page: Any, version: str) -> None:
    try:
        if current_connect_type(page) == "Android":
            apply_android_kernel_mapping(page)
    except Exception:
        logging.debug("on_android_version_changed failed", exc_info=True)


def set_refresh_ui_locked(page: Any, locked: bool) -> None:
    """Lock/unlock tree and global updates while editable info is recomputed."""
    if hasattr(page, "case_tree"):
        try:
            page.case_tree.setEnabled(not locked)
        except Exception:
            logging.debug("set_refresh_ui_locked: failed to toggle case_tree", exc_info=True)
    try:
        page.setUpdatesEnabled(not locked)
    except Exception:
        logging.debug("set_refresh_ui_locked: failed to toggle updates", exc_info=True)



def _rebalance_panel(panel: Any) -> None:
    """Request a layout rebalance on a ConfigGroupPanel, if available."""
    if panel is None or not hasattr(panel, "request_rebalance"):
        return
    try:
        panel.request_rebalance()
    except Exception:
        logging.debug("Failed to rebalance config panel", exc_info=True)


def handle_config_event(page: Any, event: str, **payload: Any) -> None:
    """Unified entry point for all Config-page UI events.

    Controllers and signal bindings should route user interactions here,
    passing a simple ``event`` string plus any structured payload
    (e.g. case path, RF model text, CSV index).  The dispatcher then
    calls the existing action helpers so that init-time and user-driven
    state changes share the same code paths.
    """
    event = str(event or "").strip() if event is not None else ""
    config_ctl = getattr(page, "config_ctl", None)

    if event == "init":
        # Initial UI pass �?derive state purely from current widget values
        # and config without forcing any particular ordering.
        try:
            case_path = getattr(page, "_current_case_path", "") or ""
        except Exception:
            case_path = ""
        if case_path and hasattr(page, "get_editable_fields"):
            page.get_editable_fields(case_path)
        # Apply connect type related UI if we have a combo bound.
        ct_combo = getattr(page, "connect_type_combo", None)
        if ct_combo is not None and hasattr(ct_combo, "currentText"):
            handle_config_event(
                page,
                "connect_type_changed",
                text=ct_combo.currentText(),
            )
        # Third-party checkbox initial state.
        third_checkbox = getattr(page, "third_party_checkbox", None)
        if isinstance(third_checkbox, QCheckBox):
            handle_config_event(
                page,
                "third_party_toggled",
                checked=third_checkbox.isChecked(),
            )
        # Serial port initial state.
        field_widgets = getattr(page, "field_widgets", {}) or {}
        serial_status = field_widgets.get("serial_port.status")
        if isinstance(serial_status, QCheckBox):
            handle_config_event(
                page,
                "serial_status_changed",
                text="True" if serial_status.isChecked() else "False",
            )
        # RF Model / RvR tool initial state.
        rf_model = field_widgets.get("rf_solution.model")
        if rf_model is not None and hasattr(rf_model, "currentText"):
            handle_config_event(
                page,
                "rf_model_changed",
                model_text=rf_model.currentText(),
            )
        rvr_tool = field_widgets.get("rvr.tool") or field_widgets.get("rvr.tool_name")
        if rvr_tool is not None and hasattr(rvr_tool, "currentText"):
            handle_config_event(
                page,
                "rvr_tool_changed",
                tool_text=rvr_tool.currentText(),
            )
        return

    if event == "case_clicked":
        # User selected a test case in the tree.
        case_path = payload.get("case_path") or ""
        display_path = payload.get("display_path") or ""

        # Keep a lightweight reference to the current case path so that
        # future "init" passes can re-apply editable fields.
        if case_path:
            setattr(page, "_current_case_path", case_path)

        # Update "Selected Test Case" text if such a field exists.
        field_widgets = getattr(page, "field_widgets", {}) or {}
        text_case = field_widgets.get("text_case")
        if text_case is not None and hasattr(text_case, "setText"):
            try:
                text_case.setText(display_path or case_path)
            except Exception:
                pass
        else:
            # Use centralized display updater for the selected test case.
            try:
                update_test_case_display(page, display_path or case_path)
            except Exception:
                logging.debug("update_test_case_display failed in case_clicked", exc_info=True)

        # Re-compute editable info + page availability.
        view = getattr(page, "view", None)
        if config_ctl is not None:
            config_ctl.get_editable_fields(case_path)
            if view is not None and hasattr(view, "set_current_page"):
                try:
                    if config_ctl.is_stability_case(case_path):
                        view.set_current_page("stability")
                    elif config_ctl.is_performance_case(case_path):
                        view.set_current_page("execution")
                except Exception as exc:
                    logging.debug("auto page switch failed: %s", exc)
        return

    if event == "settings_tab_clicked":
        key = str(payload.get("key", "")).strip()
        view = getattr(page, "view", None)
        if view is None or not hasattr(view, "set_current_page"):
            return
        view.set_current_page(key)
        return

    if event == "connect_type_changed":
        text = payload.get("text", "")
        handle_connect_type_changed(page, text)
        return

    if event == "third_party_toggled":
        checked = bool(payload.get("checked", False))
        handle_third_party_toggled(page, checked)
        return

    if event == "serial_status_changed":
        text = str(payload.get("text", ""))
        # Apply serial UI + rules regardless of the underlying widget type.
        apply_serial_enabled_ui_state(page, text)
        if hasattr(page, "_dut_panel"):
            _rebalance_panel(page._dut_panel)
        apply_config_ui_rules(page)
        return

    if event == "rf_model_changed":
        model_text = str(payload.get("model_text", ""))
        apply_rf_model_ui_state(page, model_text)
        if hasattr(page, "_execution_panel"):
            _rebalance_panel(page._execution_panel)
        return

    if event == "rvr_tool_changed":
        tool_text = str(payload.get("tool_text", ""))
        field_widgets = getattr(page, "field_widgets", {}) or {}
        ix_path = field_widgets.get("rvr.ixchariot.path")
        apply_rvr_tool_ui_state(page, tool_text)
        if hasattr(page, "_execution_panel"):
            _rebalance_panel(page._execution_panel)
        return

    if event == "router_name_changed":
        name = str(payload.get("name", ""))
        if config_ctl is not None:
            config_ctl.handle_router_name_changed(name)
        return

    if event == "router_address_changed":
        text = str(payload.get("address", ""))
        if config_ctl is not None:
            config_ctl.handle_router_address_changed(text)
        return

    if event == "csv_index_changed":
        index = int(payload.get("index", -1))
        force = bool(payload.get("force", False))
        if config_ctl is None:
            return
        csv_combo = getattr(page, "csv_combo", None)
        if csv_combo is None:
            return
        if index < 0:
            config_ctl.set_selected_csv(None, sync_combo=False)
            return
        if not hasattr(csv_combo, "itemData"):
            return
        data = csv_combo.itemData(index)
        logging.debug("handle_config_event csv_index_changed index=%s data=%s", index, data)
        new_path = config_ctl.normalize_csv_path(data)
        current = getattr(page, "selected_csv_path", None)
        if not force and new_path == current:
            return
        config_ctl.set_selected_csv(new_path, sync_combo=False)
        setattr(page, "selected_csv_path", new_path)
        signal = getattr(page, "csvFileChanged", None)
        if signal is not None and hasattr(signal, "emit"):
            signal.emit(new_path or "")

        sync_switch_wifi_on_csv_changed(page, new_path)
        return

    if event == "switch_wifi_use_router_changed":
        checked = bool(payload.get("checked", False))
        handle_switch_wifi_use_router_changed(page, checked)
        return

    if event == "switch_wifi_router_csv_changed":
        index = int(payload.get("index", -1))
        handle_switch_wifi_router_csv_changed(page, index)
        return

    if event in {
        "stability_exitfirst_changed",
        "stability_ping_changed",
        "stability_script_section_toggled",
        "stability_relay_type_changed",
        "switch_wifi_use_router_changed",
        "switch_wifi_router_csv_changed",
    }:
        # Stability Settings: test_str / test_switch_wifi duration & relay rules.
        # All concrete enable/disable logic lives in CONFIG_UI_RULES (R14–R18);
        # here we simply re-evaluate rules based on updated widget states.
        apply_config_ui_rules(page)
        return

    # Unknown events are ignored to keep the dispatcher tolerant of future
    # extensions.
    logging.debug("handle_config_event: unknown event %r payload=%r", event, payload)


def apply_rf_model_ui_state(page: Any, model_str: str) -> None:
    """Toggle RF-solution parameter fields based on the selected model.

    This replaces the legacy group-based implementation and relies directly
    on schema-generated field keys, for example:
    - ``rf_solution.RC4DAT-8G-95.*``
    - ``rf_solution.RADIORACK-4-220.ip_address``
    - ``rf_solution.LDA-908V-8.*``

    The ``RS232Board5`` model requires no extra configuration beyond the
    RF Model combo itself, so all additional fields remain hidden.
    """
    field_widgets = getattr(page, "field_widgets", {}) or {}

    def _set_field_visible(key: str, visible: bool) -> None:
        w = field_widgets.get(key)
        if w is None:
            return
        if hasattr(w, "setVisible"):
            w.setVisible(visible)
        # Also hide the label in QFormLayout-based rows.
        try:
            parent = w.parent()
            from PyQt5.QtWidgets import QFormLayout  # type: ignore

            if hasattr(parent, "layout"):
                layout = parent.layout()
                if isinstance(layout, QFormLayout):
                    label = layout.labelForField(w)
                    if label is not None and hasattr(label, "setVisible"):
                        label.setVisible(visible)
        except Exception:
            pass

    model_str = str(model_str or "").strip()

    # DEBUG PRINT: trace RF model UI invocation (remove after debugging)
    try:
        print(f"[DEBUG][RF_UI] apply_rf_model_ui_state called model_str={model_str} page={getattr(page,'objectName',lambda:None)()}" )
    except Exception:
        print(f"[DEBUG][RF_UI] apply_rf_model_ui_state called model_str={model_str}")

    # Hide all model-specific fields by default.
    for key in (
        "rf_solution.RC4DAT-8G-95.idVendor",
        "rf_solution.RC4DAT-8G-95.idProduct",
        "rf_solution.RC4DAT-8G-95.ip_address",
        "rf_solution.RADIORACK-4-220.ip_address",
        "rf_solution.LDA-908V-8.ip_address",
        "rf_solution.LDA-908V-8.channels",
    ):
        _set_field_visible(key, False)

    # RS232Board5: keep all model-specific fields hidden (no user config).
    if model_str == "RS232Board5":
        return

    if model_str == "RC4DAT-8G-95":
        for key in (
            "rf_solution.RC4DAT-8G-95.idVendor",
            "rf_solution.RC4DAT-8G-95.idProduct",
            "rf_solution.RC4DAT-8G-95.ip_address",
        ):
            _set_field_visible(key, True)
    elif model_str == "RADIORACK-4-220":
        _set_field_visible("rf_solution.RADIORACK-4-220.ip_address", True)
    elif model_str == "LDA-908V-8":
        for key in (
            "rf_solution.LDA-908V-8.ip_address",
            "rf_solution.LDA-908V-8.channels",
        ):
            _set_field_visible(key, True)


def apply_rvr_tool_ui_state(page: Any, tool: str) -> None:
    """Toggle RvR tool-specific parameter groups (iperf vs ixchariot)."""
    normalized = (tool or "").strip().lower()
    if hasattr(page, "rvr_iperf_group"):
        page.rvr_iperf_group.setVisible(normalized == "iperf")
    if hasattr(page, "rvr_ix_group"):
        page.rvr_ix_group.setVisible(normalized == "ixchariot")

    # Only allow IxChariot path edit when ixchariot is selected.
    field_widgets = getattr(page, "field_widgets", {}) or {}
    ix_path = field_widgets.get("rvr.ixchariot.path")
    if ix_path is not None and hasattr(ix_path, "setEnabled"):
        ix_path.setEnabled(normalized == "ixchariot")


def apply_serial_enabled_ui_state(page: Any, text: str) -> None:
    """Show/hide the serial config group when serial is enabled/disabled."""
      if hasattr(page, "serial_cfg_group"):
          page.serial_cfg_group.setVisible(text == "True")


  def apply_turntable_model_ui_state(page: Any, model: str) -> None:
    """Toggle visibility/enabled state for turntable IP controls."""
    if not hasattr(page, "turntable_ip_edit") or not hasattr(page, "turntable_ip_label"):
        return
    requires_ip = model == TURN_TABLE_MODEL_OTHER
    page.turntable_ip_label.setVisible(requires_ip)
    page.turntable_ip_edit.setVisible(requires_ip)
          page.turntable_ip_edit.setEnabled(requires_ip)


def set_fields_editable(page: Any, fields: set[str]) -> None:
    """Enable or disable config widgets based on the given editable field keys."""
    widgets = getattr(page, "field_widgets", {}) or {}
    for key, widget in widgets.items():
        try:
            enabled = key in fields
            if hasattr(widget, "setEnabled"):
                widget.setEnabled(enabled)
        except Exception:
            logging.debug("set_fields_editable failed for key=%s", key, exc_info=True)


def apply_run_lock_ui_state(page: Any, locked: bool) -> None:
    """Apply UI changes when a test run is locked/unlocked."""
    if hasattr(page, "case_tree"):
        page.case_tree.setEnabled(not locked)
    # Sync run button enabled state via controller helper if available.
    config_ctl = getattr(page, "config_ctl", None)
    if config_ctl is not None and hasattr(config_ctl, "sync_run_buttons_enabled"):
        try:
            config_ctl.sync_run_buttons_enabled()
        except Exception:
            pass
    if locked:
        # During a run, prevent user edits across all fields and CSV combos.
        field_widgets = getattr(page, "field_widgets", {}) or {}
        for w in field_widgets.values():
            try:
                w.setEnabled(False)
            except Exception:
                continue
        if hasattr(page, "csv_combo"):
            try:
                page.csv_combo.setEnabled(False)
            except Exception:
                pass
    else:
        # Restore editable state and navigation when unlocking.
        if hasattr(page, "config_ctl") and hasattr(page.config_ctl, "restore_editable_state"):
            try:
                page.config_ctl.restore_editable_state()
            except Exception:
                pass
        if hasattr(page, "_update_navigation_state"):
            try:
                page._update_navigation_state()
            except Exception:
                pass


def refresh_config_page_controls(page: Any) -> None:
    """Build and refresh all controls on the Config page (including FPGA mapping)."""
    # Clear cached groups so rebuilding the UI does not accumulate stale widgets.
    if hasattr(page, "_dut_groups"):
        page._dut_groups.clear()
    if hasattr(page, "_other_groups"):
        page._other_groups.clear()

    config = getattr(page, "config", None)
    if not isinstance(config, dict):
        config = {}
        page.config = config

    # Ensure a few top-level sections always exist and are dicts.
    defaults_for_dut = {
        "software_info": {},
        "hardware_info": {},
        "system": {},
    }
    for key, default in defaults_for_dut.items():
        existing = config.get(key)
        if not isinstance(existing, dict):
            config[key] = default.copy()
        else:
            config[key] = dict(existing)

    def _coerce_debug_flag(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _normalize_debug_section(raw_value: Any) -> dict[str, bool]:
        if isinstance(raw_value, dict):
            normalized = dict(raw_value)
        else:
            normalized = {"database_mode": raw_value}
        for option in ("database_mode", "skip_router", "skip_corner_rf"):
            normalized[option] = _coerce_debug_flag(normalized.get(option))
        return normalized

    config["debug"] = _normalize_debug_section(config.get("debug"))

    # Normalise connect_type / fpga / stability sections via helpers on the page.
    config_ctl = getattr(page, "config_ctl", None)

    if config_ctl is not None:
        config["connect_type"] = config_ctl.normalize_connect_type_section(
            config.get("connect_type")
        )

    linux_cfg = config.get("connect_type", {}).get("Linux")
    if isinstance(linux_cfg, dict) and "kernel_version" in linux_cfg:
        # For legacy configs, move Linux.kernel_version into system.kernel_version.
        config.setdefault("system", {})["kernel_version"] = linux_cfg.pop("kernel_version")

    if config_ctl is not None:
        config["fpga"] = config_ctl.normalize_fpga_section(config.get("fpga"))

    if config_ctl is not None:
        config["stability"] = config_ctl.normalize_stability_settings(
            config.get("stability")
        )

    # Build three panels from YAML schemas.  Parent all groups directly
    # to the corresponding ConfigGroupPanel so that layout is fully
    # owned by the view layer.
    dut_schema = load_ui_schema("dut")
    dut_panel = getattr(page, "_dut_panel", None)
    build_groups_from_schema(page, config, dut_schema, panel_key="dut", parent=dut_panel)

    exec_schema = load_ui_schema("execution")
    exec_panel = getattr(page, "_execution_panel", None)
    build_groups_from_schema(page, config, exec_schema, panel_key="execution", parent=exec_panel)
    # Bind main Performance CSV combo (Execution panel) and log RvR widgets.
    field_widgets = getattr(page, "field_widgets", {}) or {}
    csv_widget = field_widgets.get("csv_path")
    if csv_widget is not None:
        setattr(page, "csv_combo", csv_widget)
    rvr_tool = field_widgets.get("rvr.tool") or field_widgets.get("rvr.tool_name")
    ix_path = field_widgets.get("rvr.ixchariot.path")
    try:
        ix_enabled = ix_path.isEnabled() if ix_path is not None else None
    except Exception:
        ix_enabled = None

    stability_cfg = config.get("stability") or {}
    stab_schema = load_ui_schema("stability")
    stab_panel = getattr(page, "_stability_panel", None)
    build_groups_from_schema(page, stability_cfg, stab_schema, panel_key="stability", parent=stab_panel)
    # Bind common stability groups (Duration Control / Check Point).
    try:
        from src.ui.view.config import init_stability_common_groups

        init_stability_common_groups(page)
    except Exception:
        logging.debug("Failed to initialise stability common groups", exc_info=True)

    # Wire FPGA dropdowns + Control Type / Third‑party / Stability wiring.
    init_fpga_dropdowns(page)
    init_connect_type_actions(page)
    init_system_version_actions(page)
    init_stability_actions(page)
    init_switch_wifi_actions(page)
    _bind_serial_actions(page)
    _bind_turntable_actions(page)
    _bind_rf_rvr_actions(page)
    _bind_router_actions(page)
    _bind_case_tree_actions(page)
    _bind_csv_actions(page)
    _bind_run_actions(page)


def compute_editable_info(page: Any, case_path: str) -> EditableInfo:
    """Return editable fields and related UI enable state based on case name and path.

    This is a view-layer helper extracted from ``CaseConfigPage._compute_editable_info``
    so that Execution/DUT/Stability enable rules no longer live in the controller.
    """
    import os  # local import to avoid polluting module namespace

    basename = os.path.basename(case_path)
    logging.debug("testcase name %s", basename)
    logging.debug("compute_editable_info case_path=%s basename=%s", case_path, basename)

    peak_keys = {
        "rvr",
        "rvr.tool",
        "rvr.iperf.path",
        "rvr.iperf.server_cmd",
        "rvr.iperf.client_cmd",
        "rvr.ixchariot.path",
        "rvr.repeat",
    }
    rvr_keys = peak_keys | {
        "rvr.throughput_threshold",
    }
    info = EditableInfo()
    # always keep connect_type / router / serial / fpga selection editable
    info.fields |= {
        "connect_type.type",
        "connect_type.Android.device",
        "connect_type.Linux.ip",
        "connect_type.Linux.wildcard",
        "connect_type.third_party.enabled",
        "connect_type.third_party.wait_seconds",
        "router.name",
        "router.address",
        "serial_port.status",
        "serial_port.port",
        "serial_port.baud",
        "fpga.product_line",
        "fpga.project",
    }
    config_ctl = getattr(page, "config_ctl", None)

    # Peak throughput case: limited RvR controls.
    if basename == "test_wifi_peak_throughput.py":
        info.fields |= peak_keys
    # All performance cases share full RvR config and CSV enablement.
    if config_ctl is not None and config_ctl.is_performance_case(case_path):
        info.fields |= rvr_keys
        info.enable_csv = True
        info.enable_rvr_wifi = True
    # RvO cases: enable turntable related controls; 需求更新后�?    # RvO 也需�?RF Solution �?Turntable 同时可编辑�?    if "rvo" in basename:
        info.fields |= {
            "Turntable.model",
            "Turntable.ip_address",
            "Turntable.step",
            "Turntable.static_db",
            "Turntable.target_rssi",
        }
        info.fields |= {
            "rf_solution.step",
            "rf_solution.model",
            "rf_solution.RC4DAT-8G-95.idVendor",
            "rf_solution.RC4DAT-8G-95.idProduct",
            "rf_solution.RC4DAT-8G-95.ip_address",
            "rf_solution.RADIORACK-4-220.ip_address",
            "rf_solution.LDA-908V-8.ip_address",
            "rf_solution.LDA-908V-8.channels",
        }
    # RvR cases: enable RF solution section（仅 RF Solution�?
    if "rvr" in basename:
        info.fields |= {
            "rf_solution.step",
            "rf_solution.model",
            "rf_solution.RC4DAT-8G-95.idVendor",
            "rf_solution.RC4DAT-8G-95.idProduct",
            "rf_solution.RC4DAT-8G-95.ip_address",
            "rf_solution.RADIORACK-4-220.ip_address",
            "rf_solution.LDA-908V-8.ip_address",
            "rf_solution.LDA-908V-8.channels",
        }
    # Stability cases: enable Duration Control & Check Point base fields.
    if config_ctl is not None and config_ctl.is_stability_case(case_path):
        info.fields |= {
            "stability.duration_control.loop",
            "stability.duration_control.duration_hours",
            "stability.duration_control.exitfirst",
            "stability.duration_control.retry_limit",
            "stability.check_point.ping",
            "stability.check_point.ping_targets",
        }
    # Script-specific stability fields.
    if hasattr(page, "_script_case_key") and hasattr(page, "_script_groups"):
        try:
            case_key = page._script_case_key(case_path)
        except Exception:
            case_key = ""
        entry = page._script_groups.get(case_key) if case_key else None
        if entry is not None and getattr(entry, "field_keys", None):
            info.fields |= set(entry.field_keys)

    # Debug print for analysing Execution enable rules (easy to remove later).
    has_turntable = any(k.startswith("Turntable.") for k in info.fields)
    has_rf = any(k.startswith("rf_solution.") for k in info.fields)
    has_rvr = any(k.startswith("rvr.") for k in info.fields)
    return info


def apply_field_effects(
    page: Any,
    effects: FieldEffect,
    field_widgets: dict[str, Any] | None = None,
    editable_fields: set[str] | None = None,
) -> None:
    """Apply enable/disable/show/hide rule effects to a config page.

    This helper lives in the view layer (actions) but works against a generic
    ``page`` object. It replaces the old ``CaseConfigPage._apply_field_effects``
    implementation.
    """
    if not effects:
        return

    if field_widgets is None:
        field_widgets = getattr(page, "field_widgets", {}) or {}
    if editable_fields is None:
        editable_info = getattr(page, "_last_editable_info", None)
        editable_fields = getattr(editable_info, "fields", None)

    def _current_connect_type_value() -> str:
        """Best-effort current connect type label (Android/Linux/...)."""
        try:
            return current_connect_type(page)
        except Exception:
            return ""

    def _set_enabled(key: str, enabled: bool) -> None:
        widget = field_widgets.get(key)
        if widget is None:
            return
        # Kernel Version 的可编辑状态由 Control Type 决定�?        # - Android: 始终禁用（值由 Android Version 映射�?        # - Linux:   始终可编�?        if key == "system.kernel_version":
            connect_type_val = _current_connect_type_value()
            if connect_type_val == "Android":
                enabled = False
            elif connect_type_val == "Linux":
                enabled = True
        if enabled and isinstance(editable_fields, set) and editable_fields and key not in editable_fields:
            # Do not re-enable fields that are not editable for the
            # current case according to EditableInfo.
            return
        before = widget.isEnabled()
        if before == enabled:
            return
        with QSignalBlocker(widget):
            widget.setEnabled(enabled)

    def _set_visible(key: str, visible: bool) -> None:
        widget = field_widgets.get(key)
        if widget is None:
            return
        if widget.isVisible() == visible:
            return
        widget.setVisible(visible)

    for key in effects.get("enable_fields", []) or []:
        _set_enabled(key, True)
    for key in effects.get("disable_fields", []) or []:
        _set_enabled(key, False)
    for key in effects.get("show_fields", []) or []:
        _set_visible(key, True)
    for key in effects.get("hide_fields", []) or []:
        _set_visible(key, False)


def apply_config_ui_rules(page: Any) -> None:
    """Evaluate CONFIG_UI_RULES against current UI state for the given page.

    This function centralises rule evaluation for the Config page.
    """
    try:
        rules: dict[str, RuleSpec] = CONFIG_UI_RULES
    except Exception:
        return

    # Basic state used by rules.
    config_ctl = getattr(page, "config_ctl", None)
    field_widgets = getattr(page, "field_widgets", {}) or {}
    editable_fields = getattr(getattr(page, "_last_editable_info", None), "fields", None)

      # Precompute script key once for rules that depend on a specific script.
      case_path = getattr(page, "_current_case_path", "") or ""
      script_key = ""
      if case_path and config_ctl is not None and hasattr(config_ctl, "script_case_key"):
          try:
              script_key = config_ctl.script_case_key(case_path)
          except Exception:
              script_key = ""

    for rule_id, spec in rules.items():
        active = True
        trigger_case_type = spec.get("trigger_case_type")
        if trigger_case_type and config_ctl is not None:
            try:
                active = active and config_ctl.eval_case_type_flag(trigger_case_type)
            except Exception:
                active = False
        trigger_script_key = spec.get("trigger_script_key")
        if active and trigger_script_key:
            active = active and (script_key == trigger_script_key)
        trigger_field = spec.get("trigger_field")
        value = None
        if active and trigger_field and config_ctl is not None:
            try:
                value = config_ctl.get_field_value(trigger_field)
            except Exception:
                value = None
        if not active:
            continue
        effects_to_apply: list[FieldEffect] = []
        case_map = spec.get("cases") or {}
        if trigger_field and case_map and value in case_map:
            effects_to_apply.append(case_map[value])
        base_effects = spec.get("effects")
        if base_effects:
            effects_to_apply.append(base_effects)
        for eff in effects_to_apply:
            apply_field_effects(page, eff, field_widgets, editable_fields)


def update_script_config_ui(page: Any, case_path: str) -> None:
    """Update Stability script config UI to reflect the active test case.

    This helper moves the view-related logic for stability script sections
    out of ``CaseConfigPage`` so that the controller only delegates the
    operation while the view layer coordinates group visibility and layout.
    """
    if config_ctl is None or not hasattr(config_ctl, "script_case_key"):
        return
    case_key = config_ctl.script_case_key(case_path)
    changed = False
    active_entry = None
    script_groups = getattr(page, "_script_groups", {})
    if case_key not in script_groups:
        if getattr(page, "_active_script_case", None) is not None:
            page._active_script_case = None
            for entry in script_groups.values():
                if entry.group.isVisible():
                    entry.group.setVisible(False)
        if hasattr(page, "_stability_panel"):
            page._stability_panel.set_groups([])
            _rebalance_panel(page._stability_panel)
        if hasattr(page, "_refresh_script_section_states"):
            page._refresh_script_section_states()
        return
    if getattr(page, "_active_script_case", None) != case_key:
        page._active_script_case = case_key
        changed = True
    for key, entry in script_groups.items():
        visible = key == case_key
        if entry.group.isVisible() != visible:
            entry.group.setVisible(visible)
            changed = True
        if visible:
            config_ctl = getattr(page, "config_ctl", None)
            if config_ctl is not None:
                data = config_ctl.ensure_script_case_defaults(key, entry.case_path)
                config_ctl.load_script_config_into_widgets(entry, data)
            else:
                page._load_script_config_into_widgets(entry, {})
            active_entry = entry
            if key == "test_switch_wifi":
                field_widgets = getattr(page, "field_widgets", {}) or {}
                use_router = (
                    field_widgets.get("stability.cases.switch_wifi.use_router")
                    or field_widgets.get("cases.test_switch_wifi.use_router")
                )
                router_csv = (
                    field_widgets.get("stability.cases.switch_wifi.router_csv")
                    or field_widgets.get("cases.test_switch_wifi.router_csv")
                )
                if isinstance(use_router, QCheckBox) and router_csv is not None:
                    checked = use_router.isChecked()
                    handle_config_event(
                        page,
                        "switch_wifi_use_router_changed",
                        checked=bool(checked),
                    )
    if hasattr(page, "_stability_panel"):
        if active_entry is not None:
            from src.ui.view.config import compose_stability_groups

            groups = compose_stability_groups(page, active_entry)
            page._stability_panel.set_groups(groups)
        else:
            page._stability_panel.set_groups([])
        _rebalance_panel(page._stability_panel)
    if hasattr(page, "_refresh_script_section_states"):
        page._refresh_script_section_states()

def init_stability_actions(page: Any) -> None:
    """Wire Stability panel checkboxes to rule evaluation for Duration/Checkpoint."""
    field_widgets = getattr(page, "field_widgets", {}) or {}

    exitfirst = field_widgets.get("stability.duration_control.exitfirst") or field_widgets.get(
        "duration_control.exitfirst"
    )
    ping = field_widgets.get("stability.check_point.ping") or field_widgets.get("check_point.ping")

    from PyQt5.QtWidgets import QCheckBox  # local import to avoid cycles

    if isinstance(exitfirst, QCheckBox):
        exitfirst.toggled.connect(
            lambda checked: handle_config_event(
                page,
                "stability_exitfirst_changed",
                checked=bool(checked),
            )
        )
    if isinstance(ping, QCheckBox):
        ping.toggled.connect(
            lambda checked: handle_config_event(
                page,
                "stability_ping_changed",
                checked=bool(checked),
            )
        )


def init_system_version_actions(page: Any) -> None:
    """Wire Android/System version combo to existing mapping logic.

    The actual dependency (Android Version -> Kernel Version) is already
    implemented in ``CaseConfigPage._on_android_version_changed`` and
    ``_apply_android_kernel_mapping``. This helper only reconnects the
    schema-built ``system.version`` / ``system.kernel_version`` widgets
    back to those legacy handlers without re-implementing business logic.
    """
    field_widgets = getattr(page, "field_widgets", {}) or {}

    version_widget = field_widgets.get("system.version")
    kernel_widget = field_widgets.get("system.kernel_version")
    if version_widget is None or kernel_widget is None:
        return

    # Expose widgets under legacy attribute names used by CaseConfigPage.
    setattr(page, "android_version_combo", version_widget)
    setattr(page, "kernel_version_combo", kernel_widget)

    # Reconnect Android Version combo to the original handler, but keep
    # the kernel combo's enabled state controlled purely by connect_type
    # and the rule engine (CONFIG_UI_RULES).
    handler = getattr(page, "_on_android_version_changed", None)
    if not callable(handler):
        # Fall back to centralized helper if the page does not provide one.
        handler = lambda text: on_android_version_changed(page, text)

    def _on_version_changed(text: str) -> None:
        kernel = getattr(page, "kernel_version_combo", None)
        prev_enabled = kernel.isEnabled() if kernel is not None else None
        try:
            handler(text)
        except Exception:
            logging.debug("handler for android version changed failed", exc_info=True)
        if kernel is not None:
            after_handler = kernel.isEnabled()
            if prev_enabled is not None and after_handler != prev_enabled:
                kernel.setEnabled(prev_enabled)

    try:
        version_widget.currentTextChanged.connect(_on_version_changed)
    except Exception:
        logging.debug("Failed to bind _on_android_version_changed wrapper", exc_info=True)


def init_fpga_dropdowns(view: Any) -> None:
    """Wire FPGA customer/product/project combos and keep them in sync."""
    field_widgets = getattr(view, "field_widgets", {}) or {}

    customer_combo = None
    product_combo = None
    project_combo = None

    for key, widget in field_widgets.items():
        logical = str(key).strip().lower()
        if not logical.startswith("fpga."):
            continue
        if not hasattr(widget, "currentTextChanged"):
            continue
        if logical == "fpga.customer":
            customer_combo = widget
        elif logical == "fpga.product_line":
            product_combo = widget
        elif logical == "fpga.project":
            project_combo = widget

    if not (customer_combo and product_combo and project_combo):
        logging.warning("[DEBUG_FPGA] init_fpga_dropdowns: required combos missing, abort")
        return

    setattr(view, "fpga_customer_combo", customer_combo)
    setattr(view, "fpga_product_combo", product_combo)
    setattr(view, "fpga_project_combo", project_combo)

    def _sync_hidden_fields() -> None:
        """Invoke shared helper to update config + visible fields."""
        update_fpga_hidden_fields(view)

    def _on_customer_changed(text: str) -> None:
        refresh_fpga_product_lines(view, text)
        current_product = product_combo.currentText()
        refresh_fpga_projects(view, text, current_product)
        _sync_hidden_fields()

    def _on_product_changed(text: str) -> None:
        current_customer = customer_combo.currentText()
        refresh_fpga_projects(view, current_customer, text)
        _sync_hidden_fields()

    def _on_project_changed(_text: str) -> None:
        _sync_hidden_fields()

    customer_combo.currentTextChanged.connect(_on_customer_changed)
    product_combo.currentTextChanged.connect(_on_product_changed)
    project_combo.currentTextChanged.connect(_on_project_changed)

    # Initial population based on current selections.
    initial_customer = customer_combo.currentText()
    refresh_fpga_product_lines(view, initial_customer)
    initial_product = product_combo.currentText()
    refresh_fpga_projects(view, initial_customer, initial_product)
    update_fpga_hidden_fields(view)

    setattr(view, "_fpga_dropdowns_wired", True)


def refresh_fpga_product_lines(view: Any, customer: str) -> None:
    """Populate the FPGA product-line combo for a given customer."""
    combo = getattr(view, "fpga_product_combo", None)
    if combo is None:
        logging.warning("[DEBUG_FPGA] refresh_fpga_product_lines: no fpga_product_combo")
        return
    customer_upper = (customer or "").strip().upper()
    product_lines = WIFI_PRODUCT_PROJECT_MAP.get(customer_upper, {}) if customer_upper else {}
    combo.clear()
    for product_name in product_lines.keys():
        combo.addItem(product_name)
    if combo.count() == 0:
        combo.setCurrentIndex(-1)


def refresh_fpga_projects(view: Any, customer: str, product_line: str) -> None:
    """Populate the FPGA project combo for a given customer/product-line."""
    combo = getattr(view, "fpga_project_combo", None)
    if combo is None:
        logging.warning("[DEBUG_FPGA] refresh_fpga_projects: no fpga_project_combo")
        return
    customer_upper = (customer or "").strip().upper()
    product_upper = (product_line or "").strip().upper()
    projects: dict[str, Any] = {}
    if customer_upper:
        projects = WIFI_PRODUCT_PROJECT_MAP.get(customer_upper, {}).get(product_upper, {})
    elif product_upper:
        for product_lines in WIFI_PRODUCT_PROJECT_MAP.values():
            if product_upper in product_lines:
                projects = product_lines.get(product_upper, {})
                break
    combo.clear()
    for project_name in projects.keys():
        combo.addItem(project_name)
    if combo.count() == 0:
        combo.setCurrentIndex(-1)


def update_fpga_hidden_fields(page: Any) -> None:
    """Sync selected FPGA project into config and read-only detail fields."""
    customer_combo = getattr(page, "fpga_customer_combo", None)
    product_combo = getattr(page, "fpga_product_combo", None)
    project_combo = getattr(page, "fpga_project_combo", None)
    if not (customer_combo and product_combo and project_combo):
        return

    customer = (customer_combo.currentText() or "").strip().upper()
    product = (product_combo.currentText() or "").strip().upper()
    project = (project_combo.currentText() or "").strip().upper()

    info: dict[str, Any] | None = None
    config_ctl = getattr(page, "config_ctl", None)
    if product and project and config_ctl is not None:
        guessed_customer, guessed_product, guessed_project, guessed_info = config_ctl._guess_fpga_project(  # type: ignore[attr-defined]
            "",
            "",
            "",
            customer=customer,
            product_line=product,
            project=project,
        )
        if guessed_info:
            customer = guessed_customer or customer
            product = guessed_product or product
            project = guessed_project or project
            info = guessed_info

    config_ctl = getattr(page, "config_ctl", None)

    def _norm(value: Any) -> str:
        if config_ctl is not None:
            return config_ctl.normalize_fpga_token(value)  # type: ignore[attr-defined]
        return str(value or "").strip().upper()

    if product and project and info:
        normalized = {
            "customer": customer,
            "product_line": product,
            "project": project,
            "main_chip": _norm(info.get("main_chip")),
            "wifi_module": _norm(info.get("wifi_module")),
            "interface": _norm(info.get("interface")),
        }
    else:
        normalized = {
            "customer": customer,
            "product_line": product,
            "project": project,
            "main_chip": "",
            "wifi_module": "",
            "interface": "",
        }

    setattr(page, "_fpga_details", normalized)
    config = getattr(page, "config", None)
    if isinstance(config, dict):
        config["fpga"] = dict(normalized)

    field_widgets = getattr(page, "field_widgets", {}) or {}
    for key, field_key in (
        ("main_chip", "fpga.main_chip"),
        ("wifi_module", "fpga.wifi_module"),
        ("interface", "fpga.interface"),
    ):
        widget = field_widgets.get(field_key)
        if widget is not None and hasattr(widget, "setText"):
            widget.setText(normalized.get(key, "") or "")


def apply_connect_type_ui_state(page: Any, connect_type: str) -> None:
    """Toggle connect-type related controls based on selected Control Type.

    - Android: disable Linux IP, enable Android Device.
    - Linux:   enable Linux IP, disable Android Device.
    System section is handled by rules / higher-level helpers.
    """
    # Backwards-compatible group visibility.
    if hasattr(page, "adb_group"):
        page.adb_group.setVisible(connect_type == "Android")
    if hasattr(page, "telnet_group"):
        page.telnet_group.setVisible(connect_type == "Linux")

    field_widgets = getattr(page, "field_widgets", {}) or {}

    android_device = field_widgets.get("connect_type.Android.device")
    linux_ip = field_widgets.get("connect_type.Linux.ip")

    is_android = connect_type == "Android"
    is_linux = connect_type == "Linux"

    if android_device is not None and hasattr(android_device, "setEnabled"):
        android_device.setEnabled(is_android)
    if linux_ip is not None and hasattr(linux_ip, "setEnabled"):
        linux_ip.setEnabled(is_linux)


def apply_third_party_ui_state(page: Any, enabled: bool) -> None:
    """Toggle editability of the 'third_party.wait_seconds' field."""
    field_widgets = getattr(page, "field_widgets", {}) or {}
    wait_widget = field_widgets.get("connect_type.third_party.wait_seconds")
    if wait_widget is None:
        # Fallback to legacy attribute name.
        wait_widget = getattr(page, "third_party_wait_edit", None)
    if wait_widget is None or not hasattr(wait_widget, "setEnabled"):
        return
    wait_widget.setEnabled(bool(enabled))

    # Also grey-out or restore the associated label, if we can find it.
    parent = wait_widget.parent()
    layout = parent.layout() if parent is not None else None
    if isinstance(layout, QFormLayout):
        label = layout.labelForField(wait_widget)
        if isinstance(label, QLabel):
            label.setEnabled(bool(enabled))


def handle_connect_type_changed(page: Any, display_text: str) -> None:
    """Central handler for Control Type changes (UI + business rules)."""
    text = str(display_text or "")
    normalized = normalize_connect_type_label(text)

    # 1) UI: only flip Android / Linux specific controls.
    apply_connect_type_ui_state(page, normalized)

    # 2) Business logic: Android system mapping + panel layout + rules.
    try:
        update_android_system_for_connect_type(page, normalized)
    except Exception:
        logging.debug("Failed to update Android system for connect type", exc_info=True)

    if hasattr(page, "_dut_panel"):
        _rebalance_panel(page._dut_panel)

    try:
        apply_config_ui_rules(page)
    except Exception:
        logging.debug("Failed to apply config UI rules after connect type change", exc_info=True)

    # 3) System section fallback: show/hide version / kernel widgets.
    field_widgets = getattr(page, "field_widgets", {}) or {}
    version_widget = field_widgets.get("system.version")
    kernel_widget = field_widgets.get("system.kernel_version")
    is_android = normalized == "Android"

    if version_widget is not None:
        if hasattr(version_widget, "setVisible"):
            version_widget.setVisible(is_android)
        if hasattr(version_widget, "setEnabled"):
            version_widget.setEnabled(is_android)

    if kernel_widget is not None:
        if hasattr(kernel_widget, "setVisible"):
            kernel_widget.setVisible(True)
        if hasattr(kernel_widget, "isEnabled") and hasattr(kernel_widget, "setEnabled"):
            kernel_widget.setEnabled(not is_android)


def handle_third_party_toggled(page: Any, checked: bool) -> None:
    """Central handler for Third‑party checkbox toggles (UI + rules)."""
    enabled = bool(checked)
    apply_third_party_ui_state(page, enabled)
    # 重新跑一次规则，�?R02/R03 之类的效果生效�?    apply_config_ui_rules(page)


def handle_third_party_toggled_with_permission(
    page: Any,
    checked: bool,
    allow_wait_edit: bool | None,
) -> None:
    """Third‑party handler that honours rule engine's edit-permission flag."""
    enabled = bool(checked)
    if allow_wait_edit is not None:
        enabled = enabled and bool(allow_wait_edit)
    apply_third_party_ui_state(page, enabled)


def init_connect_type_actions(page: Any) -> None:
    """Discover and wire Control Type / Third‑party related widgets."""
    field_widgets = getattr(page, "field_widgets", {}) or {}

    connect_combo = field_widgets.get("connect_type.type")
    third_checkbox = field_widgets.get("connect_type.third_party.enabled")
    third_wait = field_widgets.get("connect_type.third_party.wait_seconds")

    # Wire Control Type combo -> centralized handler.
    if connect_combo is not None:
        setattr(page, "connect_type_combo", connect_combo)
        if hasattr(connect_combo, "currentTextChanged"):
            connect_combo.currentTextChanged.connect(
                lambda text: handle_config_event(page, "connect_type_changed", text=str(text))
            )
        elif hasattr(connect_combo, "currentIndexChanged"):
            connect_combo.currentIndexChanged.connect(
                lambda _idx: handle_config_event(
                    page,
                    "connect_type_changed",
                    text=connect_combo.currentText(),
                )
            )
        # Apply initial UI/logic state once via unified dispatcher.
        handle_config_event(page, "connect_type_changed", text=connect_combo.currentText())

    # Wire Third‑party checkbox -> centralized handler.
    if isinstance(third_checkbox, QCheckBox):
        setattr(page, "third_party_checkbox", third_checkbox)
        third_checkbox.toggled.connect(
            lambda checked: handle_config_event(
                page,
                "third_party_toggled",
                checked=bool(checked),
            )
        )

    # Track Wait seconds editor.
    if third_wait is not None:
        setattr(page, "third_party_wait_edit", third_wait)
        if isinstance(third_checkbox, QCheckBox):
            apply_third_party_ui_state(page, third_checkbox.isChecked())


def _bind_serial_actions(page: Any) -> None:
    """Wire serial enabled combo to pure-UI + rule handlers."""
    field_widgets = getattr(page, "field_widgets", {}) or {}
    serial_status = field_widgets.get("serial_port.status")
    if serial_status is None:
        return

    def _apply_serial(text: str) -> None:
        """Shared helper to apply serial UI + rules."""
        apply_serial_enabled_ui_state(page, text)
        if hasattr(page, "_dut_panel"):
            _rebalance_panel(page._dut_panel)
        apply_config_ui_rules(page)

    # Checkbox-based status.
    if isinstance(serial_status, QCheckBox):
        def _on_serial_toggled(checked: bool) -> None:
            handle_config_event(
                page,
                "serial_status_changed",
                text="True" if checked else "False",
            )

        serial_status.toggled.connect(_on_serial_toggled)
        _on_serial_toggled(serial_status.isChecked())
        return

    # Combo-based status (fallback for older UIs).
    if hasattr(serial_status, "currentTextChanged"):
        def _on_serial_changed(text: str) -> None:
            handle_config_event(
                page,
                "serial_status_changed",
                text=str(text),
            )

        serial_status.currentTextChanged.connect(_on_serial_changed)
        _on_serial_changed(serial_status.currentText())


def _bind_rf_rvr_actions(page: Any) -> None:
    """Wire RF / RvR related combos to the unified dispatcher."""
    field_widgets = getattr(page, "field_widgets", {}) or {}
    # DEBUG PRINT: show field widget keys when binding RF/RvR actions
    try:
        print(f"[DEBUG][RF_UI] _bind_rf_rvr_actions: keys={list(field_widgets.keys())[:30]} (len={len(field_widgets)})")
    except Exception:
        pass

    rf_model = field_widgets.get("rf_solution.model")
    rvr_tool = field_widgets.get("rvr.tool") or field_widgets.get("rvr.tool_name")

    if rf_model is not None and hasattr(rf_model, "currentTextChanged"):
        def _on_rf_model_changed(text: str) -> None:
            # DEBUG PRINT: RF model changed event (remove after debugging)
            try:
                print(f"[DEBUG][RF_UI] rf_model.currentTextChanged -> '{text}'")
            except Exception:
                pass
            handle_config_event(
                page,
                "rf_model_changed",
                model_text=str(text),
            )

        rf_model.currentTextChanged.connect(_on_rf_model_changed)
        # Apply initial RF model visibility based on the preloaded value so
        # that only the active model's fields are shown on first load.
        try:
            # DEBUG PRINT: initial RF model apply (remove after debugging)
            try:
                cnt = rf_model.count() if hasattr(rf_model, 'count') else 'N/A'
                print(f"[DEBUG][RF_UI] initial rf_model currentText='{rf_model.currentText()}' count={cnt}")
            except Exception:
                pass
            handle_config_event(
                page,
                "rf_model_changed",
                model_text=rf_model.currentText(),
            )
        except Exception:
            logging.debug("Failed to apply initial RF model UI state", exc_info=True)

    if rvr_tool is not None and hasattr(rvr_tool, "currentTextChanged"):
        rvr_tool.currentTextChanged.connect(
            lambda text: handle_config_event(
                page,
                "rvr_tool_changed",
                tool_text=str(text),
            )
        )
        # Apply initial tool selection (iperf / ixchariot) so that IxChariot
        # path enabled/disabled state matches the combo value on first load.
        try:
            handle_config_event(
                page,
                "rvr_tool_changed",
                tool_text=rvr_tool.currentText(),
            )
        except Exception:
            logging.debug("Failed to apply initial RvR tool UI state", exc_info=True)


def _bind_turntable_actions(page: Any) -> None:
    """Wire Turntable model combo to pure UI state for its IP field."""
    field_widgets = getattr(page, "field_widgets", {}) or {}

    tt_model = field_widgets.get("Turntable.model")
    tt_ip = field_widgets.get("Turntable.ip_address")

    # Resolve and cache the IP LineEdit and its label so that the shared
    # apply_turntable_model_ui_state helper can manipulate them.
    if tt_ip is not None and hasattr(tt_ip, "parent"):
        parent = tt_ip.parent()
        layout = parent.layout() if parent is not None else None
        label = layout.labelForField(tt_ip) if isinstance(layout, QFormLayout) else None
        if label is not None:
            setattr(page, "turntable_ip_edit", tt_ip)
            setattr(page, "turntable_ip_label", label)

    if tt_model is not None and hasattr(tt_model, "currentTextChanged"):
        tt_model.currentTextChanged.connect(
            lambda text: apply_turntable_model_ui_state(page, str(text))
        )
        # Apply initial model selection so that Turntable IP is only
        # editable when the user chooses the "other" model.
        try:
            apply_turntable_model_ui_state(page, tt_model.currentText())
        except Exception:
            logging.debug("Failed to apply initial Turntable UI state", exc_info=True)


def _bind_router_actions(page: Any) -> None:
    """Wire router selection and address edits to the unified dispatcher."""
    field_widgets = getattr(page, "field_widgets", {}) or {}

    router_name = field_widgets.get("router.name")
    router_addr = field_widgets.get("router.address")

    # Router name combo -> update router object + address widget + routerInfoChanged.
    if router_name is not None and hasattr(router_name, "currentTextChanged"):
        router_name.currentTextChanged.connect(
            lambda name: handle_config_event(
                page,
                "router_name_changed",
                name=str(name),
            )
        )

    # Router address edit -> keep router_obj.address + signal in sync.
    if router_addr is not None and hasattr(router_addr, "textChanged"):
        router_addr.textChanged.connect(
            lambda text: handle_config_event(
                page,
                "router_address_changed",
                address=str(text),
            )
        )


def _bind_csv_actions(page: Any) -> None:
    """Wire main CSV combo to the unified dispatcher."""
    csv_combo = getattr(page, "csv_combo", None)
    if csv_combo is None:
        return

    if hasattr(csv_combo, "activated"):
        def _on_csv_activated(index: int) -> None:
            logging.debug("on_csv_activated index=%s", index)
            handle_config_event(
                page,
                "csv_index_changed",
                index=index,
                force=True,
            )

        csv_combo.activated.connect(_on_csv_activated)

    if hasattr(csv_combo, "currentIndexChanged"):
        csv_combo.currentIndexChanged.connect(
            lambda idx: handle_config_event(
                page,
                "csv_index_changed",
                index=idx,
                force=False,
            )
        )


def _bind_case_tree_actions(page: Any) -> None:
    """Wire case tree click to the unified config dispatcher."""
    tree = getattr(page, "case_tree", None)
    if tree is None or not hasattr(tree, "clicked"):
        return

    def _on_case_tree_clicked(proxy_idx) -> None:
        model = tree.model()
        if model is None:
            return
        if isinstance(model, QSortFilterProxyModel):
            source_idx = model.mapToSource(proxy_idx)
        else:
            source_idx = proxy_idx
        fs_model = getattr(page, "fs_model", None)
        if fs_model is None or not hasattr(fs_model, "filePath"):
            return
        path = fs_model.filePath(source_idx)
        config_ctl = getattr(page, "config_ctl", None)
        try:
            base = config_ctl.get_application_base() if config_ctl is not None else None
        except Exception:
            base = None
        try:
            display_path = os.path.relpath(path, base) if base is not None else path
        except Exception:
            display_path = path
        logging.debug("on_case_tree_clicked path=%s display=%s", path, display_path)

        if os.path.isdir(path):
            if tree.isExpanded(proxy_idx):
                tree.collapse(proxy_idx)
            else:
                tree.expand(proxy_idx)
            set_fields_editable(page, set())
            return

        if not (os.path.isfile(path)
                and os.path.basename(path).startswith("test_")
                and path.endswith(".py")):
            set_fields_editable(page, set())
            return

        from pathlib import Path as _Path

        normalized_display = _Path(display_path).as_posix() if display_path else ""

        handle_config_event(
            page,
            "case_clicked",
            case_path=path,
            display_path=normalized_display,
        )

    tree.clicked.connect(_on_case_tree_clicked)


def _bind_run_actions(page: Any) -> None:
    """Wire Run buttons to the shared run proxy."""
    run_buttons = getattr(page, "_run_buttons", []) or []
    if not run_buttons:
        return

    config_ctl = getattr(page, "config_ctl", None)

    for btn in run_buttons:
        if not hasattr(btn, "clicked"):
            continue
        if config_ctl is not None and hasattr(config_ctl, "on_run"):
            btn.clicked.connect(lambda _checked=False, ctl=config_ctl: ctl.on_run())
        elif hasattr(page, "on_run"):
            # Backward-compatibility for older pages/tests.
            btn.clicked.connect(lambda _checked=False, p=page: p.on_run())


__all__ = [
    "apply_rf_model_ui_state",
    "apply_rvr_tool_ui_state",
    "apply_serial_enabled_ui_state",
    "apply_turntable_model_ui_state",
    "apply_run_lock_ui_state",
    "refresh_config_page_controls",
    "init_fpga_dropdowns",
    "refresh_fpga_product_lines",
    "refresh_fpga_projects",
    "update_fpga_hidden_fields",
    "apply_connect_type_ui_state",
    "apply_third_party_ui_state",
    "handle_connect_type_changed",
    "handle_third_party_toggled",
    "handle_third_party_toggled_with_permission",
    "update_script_config_ui",
]
