"""UI action helpers for the Config page.

"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from PyQt5.QtCore import QSignalBlocker, QTimer
from PyQt5.QtWidgets import QWidget, QCheckBox, QSpinBox
from qfluentwidgets import LineEdit, ComboBox

from src.util.constants import SWITCH_WIFI_CASE_KEY, SWITCH_WIFI_CASE_KEYS
from src.ui.model.rules import normalize_connect_type_label, current_connect_type, evaluate_all_rules
from src.ui.model.autosave import autosave_config
from src.ui.view.builder import build_groups_from_schema, load_ui_schema
from src.ui.view import bind_view_events
from src.ui.view.config.config_switch_wifi import (
    init_switch_wifi_actions,
)


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

def _notify_rvr_wifi_page_for_function_cases(page: Any, case_path: str) -> None:
    """
    Helper function to notify the RvrWifiConfigPage to load function test cases
    when a project-related case path is selected.
    """
    if not case_path:
        return

    try:
        from pathlib import Path

        # Get the application's base path
        config_ctl = getattr(page, "config_ctl", None)
        if config_ctl is None or not hasattr(config_ctl, "get_application_base"):
            return

        app_base = Path(config_ctl.get_application_base())
        project_root = app_base / "test" / "function"
        case_path_obj = Path(case_path).resolve()

        # Check if the selected path is under 'test/function/'
        if project_root in case_path_obj.parents:
            # Extract the target directory name (e.g., 'android', 'region')
            rel_path = case_path_obj.relative_to(project_root)
            if case_path_obj.is_file() and case_path_obj.suffix == '.py':
                target_dir = rel_path.parent.name
            elif case_path_obj.is_dir():
                target_dir = rel_path.name
            else:
                return

            # Find the main window and the RvrWifiConfigPage
            main_window = page.window()
            rvr_page = getattr(main_window, "rvr_wifi_config_page", None)
            if rvr_page is not None and hasattr(rvr_page, "load_function_cases_from_dirs"):
                rvr_page.load_function_cases_from_dirs([target_dir])
                logging.debug(f"Notified RvrWifiConfigPage to load from: {target_dir}")
        else:
            # If the selection is outside 'test/function/', reset the RvrWifiConfigPage
            main_window = page.window()
            rvr_page = getattr(main_window, "rvr_wifi_config_page", None)
            if rvr_page is not None and hasattr(rvr_page, "reset_function_cases"):
                rvr_page.reset_function_cases()
                logging.debug("Reset RvrWifiConfigPage as selection is outside function/")

    except Exception as e:
        logging.debug(f"Failed to notify RvrWifiConfigPage: {e}", exc_info=True)

def apply_ui(page: Any, case_path: str) -> None:
    """Recompute case-scoped UI state and apply testcase + simple rules.

    This replaces the legacy ``ConfigController.get_editable_fields`` method.
    It computes the testcase-specific editable surface, updates controller
    flags (CSV / RvR Wi-Fi), builds ``CUSTOM_TESTCASE_UI_RULES`` and finally
    evaluates the combined rule set so that field-level attributes are driven
    exclusively by the simple rule engine.
    """
    config_ctl = getattr(page, "config_ctl", None)

    if getattr(page, "_refreshing", False):
        return

    page._refreshing = True
    set_refresh_ui_locked(page, True)

    try:
        # Controller-side model flags (CSV / RvR Wi-Fi) are still derived
        # from testcase type, but field-level enabled/visible state is
        # driven solely by the rule engine.
        from src.ui.view.common import EditableInfo as EditableInfoTypeInner

        info = EditableInfoTypeInner()
        # Enable CSV/RvR Wi-Fi for performance cases.
        if config_ctl is not None:
            try:
                if hasattr(config_ctl, "is_performance_case") and config_ctl.is_performance_case(case_path):
                    info.enable_csv = True
                    info.enable_rvr_wifi = True
            except Exception:
                logging.debug("apply_ui: is_performance_case failed", exc_info=True)

        if info.enable_csv and not hasattr(page, "csv_combo"):
            info.enable_csv = False

        if config_ctl is not None:
            try:
                config_ctl.apply_editable_info(info)
            except Exception:
                logging.debug("apply_ui: apply_editable_info failed", exc_info=True)

        # Determine which logical pages should be visible.
        page_keys = getattr(page, "_current_page_keys", ["basic"])
        if config_ctl is not None:
            try:
                page_keys = config_ctl.determine_pages_for_case(case_path, info)
            except Exception:
                logging.debug("apply_ui: determine_pages_for_case failed", exc_info=True)

        try:
            from src.ui.view.config.actions import set_available_pages as _set_available_pages

            _set_available_pages(page, page_keys)
        except Exception:
            logging.debug("apply_ui: set_available_pages failed", exc_info=True)

        # Evaluate rules once: testcase-scoped rules in CUSTOM_TESTCASE_UI_RULES
        # and global simple rules in CUSTOM_SIMPLE_UI_RULES.
        try:
            evaluate_all_rules(page, "testcase.selection")
            # After testcase-scoped rules have established the editable
            # surface, run a full pass of simple rules so that Control
            # Type, Serial Port and other field-level behaviours are
            # applied based on the initial widget values.
            evaluate_all_rules(page, None)
        except Exception:
            logging.exception("apply_ui: failed to evaluate rules for testcase", exc_info=True)

        # Update the Case page content: performance cases with RvR Wi-Fi enabled
        # show the RvR Wi-Fi editor; function cases show the function list;
        # other cases keep the Case page empty.
        try:
            main_window = page.window()
            if main_window is not None:
                rvr_page = getattr(main_window, "rvr_wifi_config_page", None)
                if rvr_page is not None and hasattr(rvr_page, "set_case_mode"):
                    from src.ui.view import determine_case_category as _case_cat

                    category = _case_cat(case_path=case_path, display_path=None)
                    if category == "function":
                        rvr_page.set_case_mode("function")
                    elif info.enable_rvr_wifi:
                        rvr_page.set_case_mode("performance")
                    else:
                        rvr_page.set_case_mode("none")
        except Exception:
            logging.debug("apply_ui: failed to update case-page mode", exc_info=True)
    finally:
        set_refresh_ui_locked(page, False)
        page._refreshing = False

    if not hasattr(page, "csv_combo"):
        logging.debug("apply_ui: csv_combo disabled")
    if getattr(page, "_pending_path", None):
        path = page._pending_path
        page._pending_path = None
        QTimer.singleShot(0, lambda: apply_ui(page, path))

    _notify_rvr_wifi_page_for_function_cases(page, case_path)

def _rebalance_panel(panel: Any) -> None:
    """Request a layout rebalance on a ConfigGroupPanel, if available."""
    if panel is None or not hasattr(panel, "request_rebalance"):
        return
    try:
        panel.request_rebalance()
    except Exception:
        logging.debug("Failed to rebalance config panel", exc_info=True)


@autosave_config
def handle_config_event(page: Any, event: str, **payload: Any) -> None:
    """Adapter layer: map legacy events to UiEvent + forward."""
    event = str(event or "").strip() if event is not None else ""
    ctl = getattr(page, "config_ctl", None)
    if not ctl or not hasattr(ctl, "handle_ui_event"):
        return

    from src.ui.view.ui_adapter import UiEvent  # local import to avoid cycles

    mapping = {
        "field_changed": "field.change",
        "case_clicked": "case.select",
        "csv_changed": "csv.select",
        "csv_index_changed": "csv.select",
        "settings_tab_clicked": "tab.switch",
        "run_clicked": "action.run",
        "switch_wifi_use_router_changed": "switch_wifi.use_router",
        "switch_wifi_router_csv_changed": "switch_wifi.router_csv",
        "connect_type_changed": "connect_type.changed",
        "third_party_toggled": "connect_type.third_party",
        "serial_status_changed": "serial.status.changed",
        "rf_model_changed": "rf_model.changed",
        "rvr_tool_changed": "rvr_tool.changed",
        "router_name_changed": "router.name.changed",
        "router_address_changed": "router.address.changed",
        "stability_exitfirst_changed": "stability.exitfirst",
        "stability_ping_changed": "stability.ping",
        "stability_script_section_toggled": "stability.script_section",
        "stability_relay_type_changed": "stability.relay_type",
    }
    kind = mapping.get(event, event)

    source = str(payload.get("field") or payload.get("key") or event)
    ui_event = UiEvent(kind=kind, source=source, payload=dict(payload))
    ctl.handle_ui_event(ui_event)


def apply_rvr_tool_ui_state(page: Any, tool: str) -> None:
    """Placeholder for RvR tool-specific UI hooks.

    All field-level attribute changes (enable/disable/show/hide) are now
    handled declaratively via the rules engine.  This function intentionally
    performs no direct widget mutation so that Execution-related behaviour
    lives entirely in the model layer.
    """
    _ = page, tool


def apply_serial_enabled_ui_state(page: Any, text: str) -> None:
    """Serial UI hook placeholder.

    The enabled/disabled state of Serial Port fields is governed by the
    simple rule engine in ``rules.py``.  This helper no longer changes widget
    attributes directly; it is kept only to preserve the call surface used by
    older wiring code.
    """
    _ = page, text


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
        # Re-apply rules so field-level state is restored based on the
        # current testcase and widget values rather than the lock state.
        try:
            evaluate_all_rules(page, None)
        except Exception:
            logging.debug(
                "apply_run_lock_ui_state: evaluate_all_rules failed on unlock",
                exc_info=True,
            )
        if hasattr(page, "_update_navigation_state"):
            try:
                page._update_navigation_state()
            except Exception:
                pass


def refresh_config_page_controls(
    page: Any,
    *,
    panel_keys: Sequence[str] | None = None,
    clear_existing: bool = True,
) -> None:
    """Build and refresh all controls on the Config page."""
    selected = {str(k) for k in panel_keys} if panel_keys is not None else None

    def _want(key: str) -> bool:
        return True if selected is None else key in selected

    # Clear cached groups so rebuilding the UI does not accumulate stale widgets.
    if clear_existing:
        if hasattr(page, "_basic_groups"):
            page._basic_groups.clear()
        if hasattr(page, "_dut_groups"):
            page._dut_groups.clear()
        if hasattr(page, "_other_groups"):
            page._other_groups.clear()

    config = getattr(page, "config", None)
    if not isinstance(config, dict):
        config = {}
        page.config = config

    # Normalise connect_type / fpga sections via helpers on the page.
    config_ctl = getattr(page, "config_ctl", None)

    if config_ctl is not None:
        config["connect_type"] = config_ctl.normalize_connect_type_section(
            config.get("connect_type")
        )

    if config_ctl is not None:
        #config["project"] = config_ctl.normalize_project_section(config.get("project"))
        config["function"] = config_ctl.normalize_project_section(config.get("function"))

    # Build panels from YAML schemas.  Parent all groups directly
    # to the corresponding ConfigGroupPanel so that layout is fully
    # owned by the view layer.
    if _want("basic"):
        basic_schema = load_ui_schema("basic")
        basic_panel = getattr(page, "_basic_panel", None) or getattr(page, "_dut_panel", None)
        build_groups_from_schema(page, config, basic_schema, panel_key="basic", parent=basic_panel)

    if _want("execution"):
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

    # Wire FPGA dropdowns + Control Type / Third‑party / Stability wiring.
    if not getattr(page, "_config_common_actions_initialized", False):
        init_connect_type_actions(page)
        init_system_version_actions(page)
        setattr(page, "_config_common_actions_initialized", True)

    # Bind declarative view events for the Config page.
    if not getattr(page, "_config_view_events_bound", False):
        try:
            bind_view_events(page, "config", handle_config_event)
            setattr(page, "_config_view_events_bound", True)
        except Exception:
            logging.debug("bind_view_events(config) failed", exc_info=True)

def set_available_pages(page: Any, page_keys: list[str]) -> None:
    """Delegate logical page selection to the Config page implementation."""
    if hasattr(page, "set_available_pages"):
        page.set_available_pages(page_keys)


def apply_config_ui_rules(page: Any) -> None:
    """Legacy wrapper around the unified rule engine.

    New code should call ``evaluate_all_rules(page, None)`` directly.  This
    helper exists to keep older call sites working while all behaviour is
    migrated onto the simple-rule engine.
    """
    try:
        evaluate_all_rules(page, None)
    except Exception:
        pass


def update_script_config_ui(page: Any, case_path: str) -> None:
    """Update Stability script config UI to reflect the active test case.

    """
    config_ctl = getattr(page, "config_ctl", None)
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
        try:
            visible = key == case_key
            if entry.group.isVisible() != visible:
                entry.group.setVisible(visible)
                changed = True
            if visible:
                config_ctl = getattr(page, "config_ctl", None)
                if config_ctl is not None:
                    data = config_ctl.ensure_script_case_defaults(key, entry.case_path)
                    # Delegate actual widget population to the view-layer helper
                    try:
                        from src.ui.view.config.actions import load_script_config_into_widgets as _view_load

                        _view_load(page, entry, data)
                    except Exception:
                        try:
                            config_ctl.load_script_config_into_widgets(entry, data)
                        except Exception:
                            logging.debug("Failed to load script config into widgets", exc_info=True)
                else:
                    # Fallback to page-level implementation if present
                    loader = getattr(page, "_load_script_config_into_widgets", None)
                    if callable(loader):
                        try:
                            loader(entry, {})
                        except Exception:
                            logging.debug("Fallback page loader failed", exc_info=True)
                active_entry = entry
                if key in SWITCH_WIFI_CASE_KEYS:
                    field_widgets = getattr(page, "field_widgets", {}) or {}
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
                    if isinstance(use_router, QCheckBox) and router_csv is not None:
                        checked = use_router.isChecked()
                        handle_config_event(
                            page,
                            "switch_wifi_use_router_changed",
                            checked=bool(checked),
                        )
        except Exception as exc:
            import traceback

            traceback.print_exc()
    has_panel = hasattr(page, "_stability_panel")
    try:
        if has_panel:
            if active_entry is not None:
                from src.ui.view.config import compose_stability_groups

                groups = compose_stability_groups(page, active_entry)
                page._stability_panel.set_groups(groups)
                try:
                    titles = [g.title() for g in groups]
                except Exception:
                    titles = ["<error>"]
            else:
                page._stability_panel.set_groups([])
            _rebalance_panel(page._stability_panel)
    except Exception as exc:
        logging.info("[DEBUG layout] stability_panel exception", repr(exc))

    # 最终刷新一遍规则，让脚本区的显隐/可编辑状态与当前选择保持一致
    apply_config_ui_rules(page)


def load_script_config_into_widgets(page: Any, entry: Any, data: Mapping[str, Any] | None) -> None:
    """Populate stability script widgets from stored config data.

    This is the view-layer implementation of the old widget population
    logic. It intentionally operates on the `page` and `entry` objects and
    uses controller helpers for CSV path resolution/selection where needed.
    """
    from src.ui.view.config import script_field_key
    from src.ui.view.config.config_switch_wifi import SwitchWifiConfigPage
    from src.ui.view.config import RfStepSegmentsWidget
    from src.util.constants import (
        SWITCH_WIFI_CASE_KEY,
        SWITCH_WIFI_USE_ROUTER_FIELD,
        SWITCH_WIFI_ROUTER_CSV_FIELD,
        SWITCH_WIFI_MANUAL_ENTRIES_FIELD,
    )

    data = data or {}
    case_key = entry.case_key

    # Special handling for switch_wifi group
    if case_key == SWITCH_WIFI_CASE_KEY:
        use_router_widget = entry.widgets.get(script_field_key(case_key, SWITCH_WIFI_USE_ROUTER_FIELD))
        router_combo = entry.widgets.get(script_field_key(case_key, SWITCH_WIFI_ROUTER_CSV_FIELD))
        manual_widget = entry.widgets.get(script_field_key(case_key, SWITCH_WIFI_MANUAL_ENTRIES_FIELD))
        use_router_value = bool(data.get(SWITCH_WIFI_USE_ROUTER_FIELD))
        try:
            if isinstance(use_router_widget, QCheckBox):
                use_router_widget.setChecked(use_router_value)
        except Exception:
            logging.debug("Failed to set switch_wifi use_router widget", exc_info=True)

        router_path = None
        try:
            ctl = getattr(page, "config_ctl", None)
            if ctl is not None:
                router_path = ctl.resolve_csv_config_path(data.get(SWITCH_WIFI_ROUTER_CSV_FIELD))
        except Exception:
            router_path = None

        try:
            if isinstance(router_combo, ComboBox):
                include_placeholder = router_combo.property("switch_wifi_include_placeholder")
                use_placeholder = True if include_placeholder is None else bool(include_placeholder)
                ctl = getattr(page, "config_ctl", None)
                if ctl is not None:
                    ctl.populate_csv_combo(router_combo, router_path, include_placeholder=use_placeholder)
                    try:
                        ctl.set_selected_csv(router_path, sync_combo=True)
                    except Exception:
                        logging.debug("Failed to sync selected CSV for switch_wifi defaults", exc_info=True)
                signal = getattr(page, "csvFileChanged", None)
                if signal is not None and hasattr(signal, "emit"):
                    try:
                        signal.emit(router_path or "")
                    except Exception:
                        logging.debug("Failed to emit csvFileChanged for switch_wifi defaults", exc_info=True)
        except Exception:
            logging.debug("Failed to populate switch_wifi router combo", exc_info=True)

        try:
            if isinstance(manual_widget, SwitchWifiConfigPage):
                manual_entries = data.get(SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
                manual_widget.set_entries(manual_entries if manual_entries is not None else [])
                # Bind entriesChanged -> handle_config_event so that manual
                # Wi‑Fi edits participate in the autosave flow.
                if not getattr(manual_widget, "_entries_autosave_bound", False):
                    def _on_entries_changed() -> None:
                        handle_config_event(
                            page,
                            "field_changed",
                            field=script_field_key(case_key, SWITCH_WIFI_MANUAL_ENTRIES_FIELD),
                        )
                    manual_widget.entriesChanged.connect(_on_entries_changed)
                    setattr(manual_widget, "_entries_autosave_bound", True)
        except Exception:
            logging.debug("Failed to initialise switch_wifi manual entries editor", exc_info=True)
        return

    ac_cfg = data.get("ac", {})
    str_cfg = data.get("str", {})

    def _set_spin(key: str, raw_value: Any) -> None:
        widget = entry.widgets.get(key)
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            value = 0
        value = max(0, value)
        try:
            if isinstance(widget, QSpinBox):
                with QSignalBlocker(widget):
                    widget.setValue(value)
            elif isinstance(widget, LineEdit):
                with QSignalBlocker(widget):
                    widget.setText(str(value))
        except Exception:
            logging.debug("_set_spin failed for %s", key, exc_info=True)

    def _set_checkbox(key: str, raw_value: Any) -> None:
        widget = entry.widgets.get(key)
        try:
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(raw_value))
        except Exception:
            logging.debug("_set_checkbox failed for %s", key, exc_info=True)

    def _set_combo(key: str, raw_value: Any) -> None:
        widget = entry.widgets.get(key)
        if not isinstance(widget, ComboBox):
            return
        value = str(raw_value or "").strip()
        try:
            with QSignalBlocker(widget):
                if value:
                    index = widget.findData(value)
                    if index < 0:
                        index = next((i for i in range(widget.count()) if widget.itemText(i) == value), -1)
                    if index < 0:
                        widget.addItem(value, value)
                        index = widget.findData(value)
                    widget.setCurrentIndex(index if index >= 0 else max(widget.count() - 1, 0))
                else:
                    widget.setCurrentIndex(0 if widget.count() else -1)
        except Exception:
            logging.debug("_set_combo failed for %s", key, exc_info=True)

    _set_checkbox(script_field_key(case_key, "ac", "enabled"), ac_cfg.get("enabled"))
    _set_spin(script_field_key(case_key, "ac", "on_duration"), ac_cfg.get("on_duration"))
    _set_spin(script_field_key(case_key, "ac", "off_duration"), ac_cfg.get("off_duration"))
    _set_combo(script_field_key(case_key, "ac", "port"), ac_cfg.get("port"))
    _set_combo(script_field_key(case_key, "ac", "mode"), ac_cfg.get("mode"))

    _set_checkbox(script_field_key(case_key, "str", "enabled"), str_cfg.get("enabled"))
    _set_spin(script_field_key(case_key, "str", "on_duration"), str_cfg.get("on_duration"))
    _set_spin(script_field_key(case_key, "str", "off_duration"), str_cfg.get("off_duration"))
    _set_combo(script_field_key(case_key, "str", "port"), str_cfg.get("port"))
    _set_combo(script_field_key(case_key, "str", "mode"), str_cfg.get("mode"))

    # Additional widget types
    try:
        rf_widget = getattr(entry, "widgets", {}).get(script_field_key(case_key, "rf_solution.step"))
        if isinstance(rf_widget, RfStepSegmentsWidget):
            # RfStepSegmentsWidget expects .set_entries / similar API; use serialize logic elsewhere
            pass
    except Exception:
        pass

def init_stability_actions(page: Any) -> None:
    """Stability Duration/Checkpoint wiring is handled by the view-event table."""
    _ = page


def init_system_version_actions(page: Any) -> None:
    _ = page


def init_fpga_dropdowns(view: Any) -> None:
    _ = view
    return

    customer_combo = None
    product_combo = None
    project_combo = None

    for key, widget in field_widgets.items():
        logical = str(key).strip().lower()
        if not logical.startswith("project."):
            continue
        if not hasattr(widget, "currentTextChanged"):
            continue
        if logical == "project.customer":
            customer_combo = widget
        elif logical == "project.product_line":
            product_combo = widget
        elif logical == "project.project":
            project_combo = widget

    def _set_combo_text(combo: Any, text: str) -> None:
        """Set combo selection by exact text match."""
        combo.setCurrentIndex(combo.findText(text))

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

    # Initial population based on persisted project configuration so that
    # the first display matches YAML values.
    config = getattr(view, "config", {}) or {}
    project_cfg = config.get("project") or {}

    target_customer = project_cfg.get("customer") or customer_combo.currentText() or ""
    _set_combo_text(customer_combo, target_customer)
    refresh_fpga_product_lines(view, target_customer)

    target_product = project_cfg.get("product_line") or product_combo.currentText() or ""
    _set_combo_text(product_combo, target_product)
    refresh_fpga_projects(view, target_customer, target_product)

    target_project = project_cfg.get("project") or project_combo.currentText() or ""
    _set_combo_text(project_combo, target_project)

    update_fpga_hidden_fields(view)

    setattr(view, "_fpga_dropdowns_wired", True)


def refresh_fpga_product_lines(view: Any, customer: str) -> None:
    """Populate the FPGA product-line combo for a given customer."""
    combo = view.fpga_product_combo
    product_lines: dict[str, Any] = {}
    if customer:
        for product_name, odm_map in WIFI_PRODUCT_PROJECT_MAP.items():
            if customer in odm_map:
                product_lines[product_name] = odm_map
    combo.clear()
    for product_name in product_lines.keys():
        combo.addItem(product_name)
    if combo.count() == 0:
        combo.setCurrentIndex(-1)


def refresh_fpga_projects(view: Any, customer: str, product_line: str) -> None:
    """Populate the FPGA project combo for a given customer/product-line."""
    combo = view.fpga_project_combo
    projects: dict[str, Any] = {}
    if product_line:
        for product_name, odm_map in WIFI_PRODUCT_PROJECT_MAP.items():
            if product_name != product_line:
                continue
            if not customer:
                merged: dict[str, Any] = {}
                for project_map in odm_map.values():
                    merged.update(project_map)
                projects = merged
                break
            filtered: dict[str, Any] = {}
            project_map = odm_map.get(customer) or {}
            for project_name, info in project_map.items():
                filtered[project_name] = info
            projects = filtered
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

    customer = customer_combo.currentText() or ""
    product = product_combo.currentText() or ""
    project = project_combo.currentText() or ""

    info: dict[str, Any] | None = None
    config_ctl = getattr(page, "config_ctl", None)
    if product and project and config_ctl is not None:
        guessed_customer, guessed_product, guessed_project, guessed_info = config_ctl._find_project_in_map(  # type: ignore[attr-defined]
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
        return str(value or "")

    mass_status: list[str] = []
    odm_choices: list[str] = []
    if info:
        mass_status = list(info["mass_production_status"])
        odm_choices = [info["ODM"]]
    current_status: list[str] = []
    current_odm = ""
    config = getattr(page, "config", None)
    if isinstance(config, dict):
        project_cfg = config.get("project") or {}
        if isinstance(project_cfg, dict):
            current_odm = str(project_cfg.get("odm") or "")
            status_value = project_cfg.get("mass_production_status")
            if isinstance(status_value, list):
                current_status = [str(item) for item in status_value if str(item)]
            elif status_value:
                current_status = [str(status_value)]

    if product and project and info:
        normalized = {
            "customer": customer,
            "product_line": product,
            "project": project,
            "odm": "",
            "main_chip": _norm(info.get("main_chip")),
            "wifi_module": _norm(info.get("wifi_module")),
            "interface": _norm(info.get("interface")),
        }
        if current_odm and current_odm in odm_choices:
            normalized["odm"] = current_odm
        elif odm_choices:
            normalized["odm"] = odm_choices[0]
    else:
        normalized = {
            "customer": customer,
            "product_line": product,
            "project": project,
            "odm": current_odm,
            "main_chip": "",
            "wifi_module": "",
            "interface": "",
        }

    setattr(page, "_fpga_details", normalized)
    config = getattr(page, "config", None)
    if isinstance(config, dict):
        project_payload = dict(normalized)
        selected = [item for item in current_status if item in mass_status]
        project_payload["mass_production_status"] = (
            selected if selected else list(mass_status)
        )
        config["project"] = project_payload

    has_project = bool(project)
    ecosystem = ""
    if info:
        ecosystem = info["ecosystem"]
    connect_combo = getattr(page, "connect_type_combo", None)
    if ecosystem:
        target_type = "Linux" if ecosystem == "Linux" else "Android"
        if isinstance(config, dict):
            connect_cfg = config.setdefault("connect_type", {})
            if isinstance(connect_cfg, dict):
                connect_cfg["type"] = target_type
        if connect_combo is not None:
            set_connect_type_combo_selection(page, target_type)
            try:
                connect_combo.setCurrentText(target_type)
            except Exception:
                logging.debug("Failed to set connect_type text", exc_info=True)
        try:
            setattr(page, "_current_connect_type", lambda: target_type)
        except Exception:
            logging.debug("Failed to set _current_connect_type override", exc_info=True)
        if connect_combo is not None:
            handle_connect_type_changed(page, target_type)
    if connect_combo is not None:
        try:
            connect_combo.setEnabled(not has_project)
        except Exception:
            logging.debug("Failed to toggle connect_type combo", exc_info=True)

    field_widgets = getattr(page, "field_widgets", {}) or {}
    for key, field_key in (
        ("main_chip", "project.main_chip"),
        ("wifi_module", "project.wifi_module"),
        ("interface", "project.interface"),
    ):
        widget = field_widgets.get(field_key)
        if widget is not None and hasattr(widget, "setText"):
            widget.setText(normalized.get(key, "") or "")

    status_widget = field_widgets.get("project.mass_production_status")
    if status_widget is not None and hasattr(status_widget, "clear"):
        status_widget.clear()
        for item in mass_status:
            status_widget.addItem(item)
        selected = set(current_status) if current_status else set(mass_status)
        for idx in range(status_widget.count()):
            state = 2 if status_widget.itemText(idx) in selected else 0
            status_widget.setItemData(idx, state)

    odm_widget = field_widgets.get("project.odm")
    if odm_widget is not None and hasattr(odm_widget, "clear"):
        odm_widget.clear()
        for item in odm_choices:
            odm_widget.addItem(item)
        if odm_choices:
            target = normalized.get("odm") or ""
            if target:
                try:
                    odm_widget.setCurrentText(target)
                except Exception:
                    odm_widget.setCurrentIndex(0)
            else:
                odm_widget.setCurrentIndex(0)


def apply_connect_type_ui_state(page: Any, connect_type: str) -> None:
    """Control-type UI hook placeholder.

    All field-level attribute changes (Android vs Linux device/IP fields and
    related system widgets) are expressed via the simple rule engine in
    ``rules.py``.  This helper no longer mutates widget attributes directly
    so that the Basic section stays purely rule-driven.
    """
    _ = page, connect_type


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

    panel = getattr(page, "_basic_panel", None) or getattr(page, "_dut_panel", None)
    if panel is not None:
        _rebalance_panel(panel)

    try:
        evaluate_all_rules(page, "connect_type.type")
    except Exception:
        logging.debug("Failed to evaluate rules after connect type change", exc_info=True)

    # 3) System section fallback removed: version and kernel widgets are now
    # controlled solely via declarative rules.  By centralising
    # visibility/enabled state in the rule engine, we avoid duplicating
    # logic here and in controller code.  When the connect type changes,
    # the rule engine will react accordingly.


def handle_third_party_toggled(page: Any, checked: bool) -> None:
    """Central handler for Third‑party checkbox toggles (UI + rules)."""
    # Delegate enabling/disabling of wait_seconds to the rule engine.  The
    # rule evaluation is handled by ``evaluate_all_rules`` using the
    # ``connect_type.third_party.enabled`` trigger field.
    try:
        evaluate_all_rules(page, "connect_type.third_party.enabled")
    except Exception:
        logging.debug("Failed to evaluate rules after third-party toggle", exc_info=True)


def init_connect_type_actions(page: Any) -> None:
    """Discover and wire Control Type / Third‑party related widgets."""
    field_widgets = getattr(page, "field_widgets", {}) or {}

    connect_combo = field_widgets.get("connect_type.type")
    third_checkbox = field_widgets.get("connect_type.third_party.enabled")
    third_wait = field_widgets.get("connect_type.third_party.wait_seconds")

    # Store references for other helpers (rules + controller).  Actual signal
    # wiring for connect_type / third-party is driven by the view-event table.
    if connect_combo is not None:
        setattr(page, "connect_type_combo", connect_combo)
    if isinstance(third_checkbox, QCheckBox):
        setattr(page, "third_party_checkbox", third_checkbox)
    if third_wait is not None:
        setattr(page, "third_party_wait_edit", third_wait)


__all__ = [
    "apply_rvr_tool_ui_state",
    "apply_ui",
    "apply_serial_enabled_ui_state",
    "apply_run_lock_ui_state",
    "refresh_config_page_controls",
    "init_fpga_dropdowns",
    "refresh_fpga_product_lines",
    "refresh_fpga_projects",
    "update_fpga_hidden_fields",
    "apply_connect_type_ui_state",
    "handle_connect_type_changed",
    "handle_third_party_toggled",
    "update_script_config_ui",
]
