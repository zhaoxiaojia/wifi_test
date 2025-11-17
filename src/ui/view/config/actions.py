"""UI action helpers for the Config page.

These functions live in the *view* layer and encapsulate pure UI behaviour
for CaseConfigPage and ConfigView (show/hide groups, enable/disable fields,
update step indicators, etc.).  Controllers should delegate visual tweaks
to these helpers instead of hard-coding widget manipulation.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from PyQt5.QtCore import QSortFilterProxyModel, QSignalBlocker
from PyQt5.QtWidgets import QWidget, QCheckBox, QFormLayout, QLabel

from src.util.constants import TURN_TABLE_MODEL_OTHER, WIFI_PRODUCT_PROJECT_MAP
from src.ui.model.rules import FieldEffect, RuleSpec, CONFIG_UI_RULES
from src.ui.view.builder import build_groups_from_schema, load_ui_schema
from src.ui.view.common import EditableInfo


def handle_config_event(page: Any, event: str, **payload: Any) -> None:
    """Unified entry point for all Config-page UI events.

    Controllers and signal bindings should route user interactions here,
    passing a simple ``event`` string plus any structured payload
    (e.g. case path, RF model text, CSV index).  The dispatcher then
    calls the existing action helpers so that init-time and user-driven
    state changes share the same code paths.
    """
    event = str(event or "").strip()

    if event == "init":
        # Initial UI pass – derive state purely from current widget values
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
        case_path = payload.get("case_path") or ""
        if hasattr(page, "get_editable_fields"):
            page.get_editable_fields(case_path)
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
        # Reuse existing serial helper behaviour by simulating a status change.
        field_widgets = getattr(page, "field_widgets", {}) or {}
        serial_status = field_widgets.get("serial_port.status")
        if isinstance(serial_status, QCheckBox):
            apply_serial_enabled_ui_state(page, text)
            if hasattr(page, "_request_rebalance_for_panels") and hasattr(page, "_dut_panel"):
                page._request_rebalance_for_panels(page._dut_panel)
            apply_config_ui_rules(page)
        return

    if event == "rf_model_changed":
        model_text = str(payload.get("model_text", ""))
        apply_rf_model_ui_state(page, model_text)
        if hasattr(page, "_request_rebalance_for_panels") and hasattr(page, "_execution_panel"):
            page._request_rebalance_for_panels(page._execution_panel)
        return

    if event == "rvr_tool_changed":
        tool_text = str(payload.get("tool_text", ""))
        apply_rvr_tool_ui_state(page, tool_text)
        if hasattr(page, "_request_rebalance_for_panels") and hasattr(page, "_execution_panel"):
            page._request_rebalance_for_panels(page._execution_panel)
        return

    if event == "router_name_changed":
        name = str(payload.get("name", ""))
        try:
            from src.tools.router_tool.router_factory import get_router  # type: ignore
        except Exception:
            return
        cfg = getattr(page, "config", {}) or {}
        router_cfg = cfg.get("router", {}) if isinstance(cfg, dict) else {}
        addr = router_cfg.get("address") if router_cfg.get("name") == name else None
        router_obj = get_router(name, addr)
        setattr(page, "router_obj", router_obj)
        field_widgets = getattr(page, "field_widgets", {}) or {}
        router_addr_widget = field_widgets.get("router.address")
        if router_addr_widget is not None and hasattr(router_addr_widget, "setText"):
            try:
                router_addr_widget.setText(router_obj.address)
            except Exception:
                pass
        signal = getattr(page, "routerInfoChanged", None)
        if signal is not None and hasattr(signal, "emit"):
            signal.emit()
        return

    if event == "router_address_changed":
        text = str(payload.get("address", ""))
        router_obj = getattr(page, "router_obj", None)
        if router_obj is not None:
            router_obj.address = text
        signal = getattr(page, "routerInfoChanged", None)
        if signal is not None and hasattr(signal, "emit"):
            signal.emit()
        return

    if event == "csv_index_changed":
        index = int(payload.get("index", -1))
        csv_combo = getattr(page, "csv_combo", None)
        if csv_combo is None:
            return
        if index < 0:
            if hasattr(page, "_set_selected_csv"):
                page._set_selected_csv(None, sync_combo=False)
            return
        if not hasattr(csv_combo, "itemData"):
            return
        data = csv_combo.itemData(index)
        logging.debug("handle_config_event csv_index_changed index=%s data=%s", index, data)
        normalizer = getattr(page, "_normalize_csv_path", None)
        new_path = normalizer(data) if callable(normalizer) else data
        current = getattr(page, "selected_csv_path", None)
        if new_path == current:
            return
        if hasattr(page, "_set_selected_csv"):
            page._set_selected_csv(new_path, sync_combo=False)
        setattr(page, "selected_csv_path", new_path)
        signal = getattr(page, "csvFileChanged", None)
        if signal is not None and hasattr(signal, "emit"):
            signal.emit(new_path or "")
        return

    # Unknown events are ignored to keep the dispatcher tolerant of future
    # extensions.
    logging.debug("handle_config_event: unknown event %r payload=%r", event, payload)


def update_step_indicator(page: Any, index: int) -> None:
    """Update the wizard step indicator to reflect the current page index."""
    view = getattr(page, "step_view_widget", None)
    if view is None:
        return
    for attr in ("setCurrentIndex", "setCurrentStep", "setCurrentRow", "setCurrent"):
        if hasattr(view, attr):
            try:
                getattr(view, attr)(index)
                return
            except Exception:
                continue
    if hasattr(view, "set_current_index"):
        try:
            view.set_current_index(index)
        except Exception:
            pass


def apply_rf_model_ui_state(page: Any, model_str: str) -> None:
    """Toggle RF-solution parameter fields based on the selected model.

    This replaces the旧基于 group 的实现，直接依赖 schema 生成的字段 key：
    - ``rf_solution.RC4DAT-8G-95.*``
    - ``rf_solution.RADIORACK-4-220.ip_address``
    - ``rf_solution.LDA-908V-8.*``
    RS232Board5 作为“无需配置”的模型，只保留 RF Model 下拉本身，其余字段全部隐藏。
    """
    field_widgets = getattr(page, "field_widgets", {}) or {}

    def _set_field_visible(key: str, visible: bool) -> None:
        w = field_widgets.get(key)
        if w is None:
            return
        if hasattr(w, "setVisible"):
            w.setVisible(visible)
        # 同步隐藏 label（QFormLayout 场景下）
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

    # 默认全部隐藏具体型号字段
    for key in (
        "rf_solution.RC4DAT-8G-95.idVendor",
        "rf_solution.RC4DAT-8G-95.idProduct",
        "rf_solution.RC4DAT-8G-95.ip_address",
        "rf_solution.RADIORACK-4-220.ip_address",
        "rf_solution.LDA-908V-8.ip_address",
        "rf_solution.LDA-908V-8.channels",
    ):
        _set_field_visible(key, False)

    # RS232Board5：无需用户配置，维持默认 all hidden。
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
    if hasattr(page, "rvr_iperf_group"):
        page.rvr_iperf_group.setVisible(tool == "iperf")
    if hasattr(page, "rvr_ix_group"):
        page.rvr_ix_group.setVisible(tool == "ixchariot")


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


def apply_run_lock_ui_state(page: Any, locked: bool) -> None:
    """Apply UI changes when a test run is locked/unlocked."""
    if hasattr(page, "case_tree"):
        page.case_tree.setEnabled(not locked)
    # Sync run button enabled state via controller helper if available.
    if hasattr(page, "_sync_run_buttons_enabled"):
        try:
            page._sync_run_buttons_enabled()
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
        if hasattr(page, "_restore_editable_state"):
            try:
                page._restore_editable_state()
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
    if hasattr(page, "_normalize_connect_type_section"):
        config["connect_type"] = page._normalize_connect_type_section(config.get("connect_type"))

    linux_cfg = config.get("connect_type", {}).get("Linux")
    if isinstance(linux_cfg, dict) and "kernel_version" in linux_cfg:
        # For legacy configs, move Linux.kernel_version into system.kernel_version.
        config.setdefault("system", {})["kernel_version"] = linux_cfg.pop("kernel_version")

    if hasattr(page, "_normalize_fpga_section"):
        config["fpga"] = page._normalize_fpga_section(config.get("fpga"))

    if hasattr(page, "_normalize_stability_settings"):
        config["stability"] = page._normalize_stability_settings(config.get("stability"))

    # Build three panels from YAML schemas.  Parent all groups directly
    # to the corresponding ConfigGroupPanel so that layout is fully
    # owned by the view layer.
    dut_schema = load_ui_schema("dut")
    dut_panel = getattr(page, "_dut_panel", None)
    build_groups_from_schema(page, config, dut_schema, panel_key="dut", parent=dut_panel)

    exec_schema = load_ui_schema("execution")
    exec_panel = getattr(page, "_execution_panel", None)
    build_groups_from_schema(page, config, exec_schema, panel_key="execution", parent=exec_panel)

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

    # Wire FPGA dropdowns + Control Type / Third‑party wiring.
    init_fpga_dropdowns(page)
    init_connect_type_actions(page)
    init_system_version_actions(page)
    _bind_serial_actions(page)
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
    # Peak throughput case: limited RvR controls.
    if basename == "test_wifi_peak_throughput.py":
        info.fields |= peak_keys
    # All performance cases share full RvR config and CSV enablement.
    if hasattr(page, "_is_performance_case") and page._is_performance_case(case_path):
        info.fields |= rvr_keys
        info.enable_csv = True
        info.enable_rvr_wifi = True
    # RvO cases: enable turntable related controls; 需求更新后，
    # RvO 也需要 RF Solution 与 Turntable 同时可编辑。
    if "rvo" in basename:
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
    # RvR cases: enable RF solution section（仅 RF Solution）.
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
    if hasattr(page, "_is_stability_case") and page._is_stability_case(case_path):
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
    print(
        "[DEBUG_EXEC_EDITABLE] basename=",
        basename,
        "has_turntable=",
        has_turntable,
        "has_rf_solution=",
        has_rf,
        "has_rvr=",
        has_rvr,
    )
    return info


def apply_field_effects(page: Any, effects: FieldEffect) -> None:
    """Apply enable/disable/show/hide rule effects to a config page.

    This helper lives in the view layer (actions) but works against a generic
    ``page`` object that exposes ``field_widgets`` and ``_last_editable_info``.
    It replaces the old ``CaseConfigPage._apply_field_effects`` implementation.
    """
    if not effects:
        return

    field_widgets = getattr(page, "field_widgets", {}) or {}
    editable_info = getattr(page, "_last_editable_info", None)
    editable_fields = getattr(editable_info, "fields", None)

    def _current_connect_type_value() -> str:
        """Best-effort current connect type label (Android/Linux/...)."""
        ct_val = ""
        try:
            if hasattr(page, "_current_connect_type"):
                ct_val = page._current_connect_type() or ""
            elif hasattr(page, "connect_type_combo") and hasattr(page.connect_type_combo, "currentText"):
                ct_val = page.connect_type_combo.currentText().strip()
                if hasattr(page, "_normalize_connect_type_label"):
                    ct_val = page._normalize_connect_type_label(ct_val)
        except Exception:
            ct_val = ""
    return ct_val

    def _set_enabled(key: str, enabled: bool) -> None:
        widget = field_widgets.get(key)
        if widget is None:
            return
        # Kernel Version 的可编辑状态由 Control Type 决定：
        # - Android: 始终禁用（值由 Android Version 映射）
        # - Linux:   始终可编辑
        if key == "system.kernel_version":
            connect_type_val = _current_connect_type_value()
            if connect_type_val == "Android":
                enabled = False
            elif connect_type_val == "Linux":
                enabled = True
        if enabled and isinstance(editable_fields, set) and editable_fields and key not in editable_fields:
            # Do not re-enable fields that are not editable for the
            # current case according to EditableInfo.
            if key.startswith(("Turntable.", "rf_solution.", "rvr.")):
                print(
                    "[DEBUG_EXEC_ENABLE] skip key=",
                    key,
                    "enabled=",
                    enabled,
                    "not in editable_fields",
                )
            return
        before = widget.isEnabled()
        if before == enabled:
            return
        with QSignalBlocker(widget):
            widget.setEnabled(enabled)
        after = widget.isEnabled()
        if key.startswith(("Turntable.", "rf_solution.", "rvr.")):
            print(
                "[DEBUG_EXEC_ENABLE] apply key=",
                key,
                "from",
                before,
                "to",
                after,
            )

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

    This function centralises rule evaluation for the Config page.  It expects
    ``page`` to expose:
    - ``field_widgets: dict[str, QWidget]``
    - ``_last_editable_info`` with ``fields`` attribute (EditableInfo)
    - ``_current_case_path`` and ``_script_case_key`` (optional)
    - ``_eval_case_type_flag(flag: str) -> bool``
    - ``_get_field_value(field_key: str) -> Any``
    """
    try:
        rules: dict[str, RuleSpec] = CONFIG_UI_RULES
    except Exception:
        return

    # Precompute script key once for rules that depend on a specific script.
    case_path = getattr(page, "_current_case_path", "") or ""
    script_key = ""
    if case_path and hasattr(page, "_script_case_key"):
        try:
            script_key = page._script_case_key(case_path)
        except Exception:
            script_key = ""

    for rule_id, spec in rules.items():
        active = True
        trigger_case_type = spec.get("trigger_case_type")
        if trigger_case_type and hasattr(page, "_eval_case_type_flag"):
            try:
                active = active and page._eval_case_type_flag(trigger_case_type)
            except Exception:
                active = False
        trigger_script_key = spec.get("trigger_script_key")
        if active and trigger_script_key:
            active = active and (script_key == trigger_script_key)
        trigger_field = spec.get("trigger_field")
        value = None
        if active and trigger_field and hasattr(page, "_get_field_value"):
            try:
                value = page._get_field_value(trigger_field)
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
            apply_field_effects(page, eff)


def init_system_version_actions(page: Any) -> None:
    """Wire Android/System version combo to existing mapping logic.

    The actual dependency (Android Version -> Kernel Version) is already
    implemented in ``CaseConfigPage._on_android_version_changed`` and
    ``_apply_android_kernel_mapping``.  Here我们只负责把 schema 构建出来的
    ``system.version`` / ``system.kernel_version`` 控件挂回到这些已有方法上，
    不重新实现任何业务逻辑。
    """
    field_widgets = getattr(page, "field_widgets", {}) or {}

    version_widget = field_widgets.get("system.version")
    kernel_widget = field_widgets.get("system.kernel_version")
    if version_widget is None or kernel_widget is None:
        return

    # 挂回旧代码依赖的属性名，保持 CaseConfigPage 里的实现不变。
    setattr(page, "android_version_combo", version_widget)
    setattr(page, "kernel_version_combo", kernel_widget)

    # 把 Android Version 的变化重新接回原来的 _on_android_version_changed，
    # 但在调用前后保持 kernel combo 的 enabled 状态不变（是否可编辑仍由
    # connect_type 和规则统一控制）。
    original_handler = getattr(page, "_on_android_version_changed", None)
    if callable(original_handler) and hasattr(version_widget, "currentTextChanged"):
        def _on_version_changed(text: str) -> None:
            kernel = getattr(page, "kernel_version_combo", None)
            prev_enabled = kernel.isEnabled() if kernel is not None else None
            print(
                "[DEBUG_KERNEL_VERSION] before _on_android_version_changed: enabled=",
                prev_enabled, "android_version=", text
            )
            original_handler(text)
            if kernel is not None:
                after_handler = kernel.isEnabled()
                if prev_enabled is not None and after_handler != prev_enabled:
                    kernel.setEnabled(prev_enabled)
                print(
                    "[DEBUG_KERNEL_VERSION] after mapping: enabled=",
                    kernel.isEnabled(), "android_version=", text
                )

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
    if product and project and hasattr(page, "_guess_fpga_project"):
        guessed_customer, guessed_product, guessed_project, guessed_info = page._guess_fpga_project(
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

    normalize_token = getattr(page, "_normalize_fpga_token", None)

    def _norm(value: Any) -> str:
        if callable(normalize_token):
            return normalize_token(value)
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
    normalized = text
    if hasattr(page, "_normalize_connect_type_label"):
        normalized = page._normalize_connect_type_label(text)

    # 1) UI: only flip Android / Linux specific controls.
    apply_connect_type_ui_state(page, normalized)

    # 2) Business logic: Android system mapping + panel layout + rules.
    if hasattr(page, "_update_android_system_for_connect_type"):
        try:
            page._update_android_system_for_connect_type(normalized)
        except Exception:
            logging.debug("Failed to update Android system for connect type", exc_info=True)

    if hasattr(page, "_request_rebalance_for_panels") and hasattr(page, "_dut_panel"):
        try:
            page._request_rebalance_for_panels(page._dut_panel)
        except Exception:
            logging.debug("Failed to rebalance panels after connect type change", exc_info=True)

    # 让规则引擎根据新的 connect_type 重新计算 enable/disable。
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
    # 重新跑一次规则，让 R02/R03 之类的效果生效。
    apply_config_ui_rules(page)


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
                lambda text: handle_connect_type_changed(page, text)
            )
        elif hasattr(connect_combo, "currentIndexChanged"):
            connect_combo.currentIndexChanged.connect(
                lambda _idx: handle_connect_type_changed(page, connect_combo.currentText())
            )
        # Apply initial UI/logic state once.
        handle_connect_type_changed(page, connect_combo.currentText())

    # Wire Third‑party checkbox -> centralized handler.
    if isinstance(third_checkbox, QCheckBox):
        setattr(page, "third_party_checkbox", third_checkbox)
        third_checkbox.toggled.connect(lambda checked: handle_third_party_toggled(page, checked))

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
        if hasattr(page, "_request_rebalance_for_panels") and hasattr(page, "_dut_panel"):
            page._request_rebalance_for_panels(page._dut_panel)
        # 触发 R03，让 Port/Baud 的 enabled 状态根据 serial_port.status 更新。
        apply_config_ui_rules(page)

    # Checkbox-based status.
    if isinstance(serial_status, QCheckBox):
        def _on_serial_toggled(checked: bool) -> None:
            _apply_serial("True" if checked else "False")

        serial_status.toggled.connect(_on_serial_toggled)
        _on_serial_toggled(serial_status.isChecked())
        return

    # Combo-based status (fallback for older UIs).
    if hasattr(serial_status, "currentTextChanged"):
        def _on_serial_changed(text: str) -> None:
            _apply_serial(str(text))

        serial_status.currentTextChanged.connect(_on_serial_changed)
        _on_serial_changed(serial_status.currentText())


def _bind_rf_rvr_actions(page: Any) -> None:
    """Wire RF / RvR related combos to UI helpers and layout refresh."""
    field_widgets = getattr(page, "field_widgets", {}) or {}

    rf_model = field_widgets.get("rf_solution.model")
    rvr_tool = field_widgets.get("rvr.tool") or field_widgets.get("rvr.tool_name")

    if rf_model is not None and hasattr(rf_model, "currentTextChanged"):
        def _on_rf_model_changed(text: str) -> None:
            apply_rf_model_ui_state(page, text)
            if hasattr(page, "_request_rebalance_for_panels") and hasattr(page, "_execution_panel"):
                page._request_rebalance_for_panels(page._execution_panel)

        rf_model.currentTextChanged.connect(_on_rf_model_changed)
        # Apply initial RF model visibility based on the preloaded value so
        # that only the active model's fields are shown on first load.
        try:
            _on_rf_model_changed(rf_model.currentText())
        except Exception:
            logging.debug("Failed to apply initial RF model UI state", exc_info=True)

    if rvr_tool is not None and hasattr(rvr_tool, "currentTextChanged"):
        def _on_rvr_tool_changed(text: str) -> None:
            apply_rvr_tool_ui_state(page, text)
            if hasattr(page, "_request_rebalance_for_panels") and hasattr(page, "_execution_panel"):
                page._request_rebalance_for_panels(page._execution_panel)

        rvr_tool.currentTextChanged.connect(_on_rvr_tool_changed)


def _bind_router_actions(page: Any) -> None:
    """Wire router selection and address edits to router model + CSV refresh."""
    field_widgets = getattr(page, "field_widgets", {}) or {}

    router_name = field_widgets.get("router.name")
    router_addr = field_widgets.get("router.address")

    # Router name combo -> update router object + address widget + routerInfoChanged.
    if router_name is not None and hasattr(router_name, "currentTextChanged"):
        def _on_router_changed(name: str) -> None:
            from src.tools.router_tool.router_factory import get_router  # local import to avoid cycles

            cfg = getattr(page, "config", {}) or {}
            router_cfg = cfg.get("router", {}) if isinstance(cfg, dict) else {}
            addr = router_cfg.get("address") if router_cfg.get("name") == name else None
            router_obj = get_router(name, addr)
            setattr(page, "router_obj", router_obj)

            if router_addr is not None and hasattr(router_addr, "setText"):
                try:
                    router_addr.setText(router_obj.address)
                except Exception:
                    pass

            signal = getattr(page, "routerInfoChanged", None)
            if signal is not None and hasattr(signal, "emit"):
                signal.emit()

        router_name.currentTextChanged.connect(_on_router_changed)

    # Router address edit -> keep router_obj.address + signal in sync.
    if router_addr is not None and hasattr(router_addr, "textChanged"):
        def _on_router_addr_changed(text: str) -> None:
            router_obj = getattr(page, "router_obj", None)
            if router_obj is not None:
                router_obj.address = text
            signal = getattr(page, "routerInfoChanged", None)
            if signal is not None and hasattr(signal, "emit"):
                signal.emit()

        router_addr.textChanged.connect(_on_router_addr_changed)


def _bind_case_tree_actions(page: Any) -> None:
    """Wire case tree click to controller handler that updates selected case."""
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
        try:
            base = getattr(page, "_get_application_base")()
        except Exception:
            base = None
        try:
            display_path = os.path.relpath(path, base) if base is not None else path
        except Exception:
            display_path = path
        logging.debug("on_case_tree_clicked path=%s display=%s", path, display_path)
        try:
            is_perf = getattr(page, "_is_performance_case")(path)
        except Exception:
            is_perf = False
        logging.debug("on_case_tree_clicked is_performance=%s", is_perf)

        if os.path.isdir(path):
            if tree.isExpanded(proxy_idx):
                tree.collapse(proxy_idx)
            else:
                tree.expand(proxy_idx)
            if hasattr(page, "set_fields_editable"):
                page.set_fields_editable(set())
            return

        if not (os.path.isfile(path)
                and os.path.basename(path).startswith("test_")
                and path.endswith(".py")):
            if hasattr(page, "set_fields_editable"):
                page.set_fields_editable(set())
            return

        from pathlib import Path as _Path

        normalized_display = _Path(display_path).as_posix() if display_path else ""
        # 更新当前用例显示（右上角路径等）
        if hasattr(page, "_update_test_case_display"):
            page._update_test_case_display(normalized_display)
        # 触发可编辑字段和页面集合的逻辑（包括 DUT / Execution / Stability 标签）
        if hasattr(page, "get_editable_fields"):
            page.get_editable_fields(path)

    tree.clicked.connect(_on_case_tree_clicked)


def _bind_csv_actions(page: Any) -> None:
    """Wire main CSV combo to selection-change handler + signal."""
    csv_combo = getattr(page, "csv_combo", None)
    if csv_combo is None:
        return

    if hasattr(csv_combo, "activated"):
        def _on_csv_activated(index: int) -> None:
            logging.debug("on_csv_activated index=%s", index)
            _on_csv_changed(index, force=True)

        csv_combo.activated.connect(_on_csv_activated)

    def _on_csv_changed(index: int, force: bool = False) -> None:
        if index < 0:
            if hasattr(page, "_set_selected_csv"):
                page._set_selected_csv(None, sync_combo=False)
            return
        if not hasattr(csv_combo, "itemData"):
            return
        data = csv_combo.itemData(index)
        logging.debug("on_csv_changed index=%s data=%s", index, data)
        normalizer = getattr(page, "_normalize_csv_path", None)
        new_path = normalizer(data) if callable(normalizer) else data
        current = getattr(page, "selected_csv_path", None)
        if not force and new_path == current:
            return
        if hasattr(page, "_set_selected_csv"):
            page._set_selected_csv(new_path, sync_combo=False)
        setattr(page, "selected_csv_path", new_path)
        logging.debug("selected_csv_path=%s", new_path)
        signal = getattr(page, "csvFileChanged", None)
        if signal is not None and hasattr(signal, "emit"):
            signal.emit(new_path or "")

    if hasattr(csv_combo, "currentIndexChanged"):
        csv_combo.currentIndexChanged.connect(
            lambda idx: _on_csv_changed(idx, force=False)
        )


def _bind_run_actions(page: Any) -> None:
    """Wire Run buttons to the shared run proxy."""
    run_buttons = getattr(page, "_run_buttons", []) or []
    if not run_buttons:
        return

    from src.ui.run_proxy import on_run as _proxy_on_run

    for btn in run_buttons:
        if not hasattr(btn, "clicked"):
            continue
        btn.clicked.connect(lambda _checked=False, p=page: _proxy_on_run(p))


__all__ = [
    "update_step_indicator",
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
]
