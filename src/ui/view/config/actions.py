"""UI action helpers for the Config page.

"""

from __future__ import annotations

import logging
import os
from typing import Any, Sequence, Mapping

from PyQt5.QtCore import QSortFilterProxyModel, QSignalBlocker, QTimer
from PyQt5.QtWidgets import QWidget, QCheckBox, QFormLayout, QLabel, QSpinBox, QDoubleSpinBox
from qfluentwidgets import LineEdit, ComboBox

from src.util.constants import (
    WIFI_PRODUCT_PROJECT_MAP,
    ANDROID_KERNEL_MAP,
    SWITCH_WIFI_CASE_KEY,
    SWITCH_WIFI_CASE_KEYS,
)
from src.ui.model.rules import normalize_connect_type_label, current_connect_type, evaluate_all_rules
from src.ui.model.autosave import autosave_config
from src.ui.view.builder import build_groups_from_schema, load_ui_schema
from src.ui.view import bind_view_events, determine_case_category
from src.ui.view.config.config_switch_wifi import (
    sync_switch_wifi_on_csv_changed,
    handle_switch_wifi_use_router_changed,
    handle_switch_wifi_router_csv_changed,
    init_switch_wifi_actions,
)
from src import display_to_case_path, case_path_to_display, update_test_case_display


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


def _refresh_case_page_compatibility(page: Any) -> None:
    """Refresh the Case-page compatibility selection to mirror config state."""
    try:
        main_window = page.window()
    except Exception:
        main_window = None
    if main_window is None:
        return
    rvr_page = getattr(main_window, "rvr_wifi_config_page", None)
    if rvr_page is None or not hasattr(rvr_page, "set_case_mode"):
        return
    try:
        from src.ui.view import determine_case_category  # local import to avoid cycles
    except Exception:
        determine_case_category = None  # type: ignore[assignment]
    try:
        case_path = getattr(page, "_current_case_path", "") or ""
    except Exception:
        case_path = ""
    if determine_case_category is not None:
        try:
            category = determine_case_category(case_path=case_path, display_path=None)
        except Exception:
            category = None
        if category != "compatibility":
            return
    try:
        rvr_page.set_case_mode("compatibility")
    except Exception:
        logging.debug("Failed to refresh Case page compatibility selection", exc_info=True)


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
        # Script-specific stability UI (test_str / switch_wifi, etc.).
        try:
            update_script_config_ui(page, case_path)
        except Exception:
            logging.debug("apply_ui: update_script_config_ui failed", exc_info=True)

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
        page_keys = getattr(page, "_current_page_keys", ["dut"])
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

        # Update the Case page content: performance cases with RvR Wi‑Fi
        # enabled show the RvR Wi‑Fi editor; compatibility cases show the
        # compatibility router list; other cases keep the Case page empty.
        try:
            main_window = page.window()
            if main_window is not None:
                rvr_page = getattr(main_window, "rvr_wifi_config_page", None)
                if rvr_page is not None and hasattr(rvr_page, "set_case_mode"):
                    from src.ui.view import determine_case_category as _case_cat

                    category = _case_cat(case_path=case_path, display_path=None)
                    if category == "compatibility":
                        rvr_page.set_case_mode("compatibility")
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



def _rebalance_panel(panel: Any) -> None:
    """Request a layout rebalance on a ConfigGroupPanel, if available."""
    if panel is None or not hasattr(panel, "request_rebalance"):
        return
    try:
        panel.request_rebalance()
    except Exception:
        logging.debug("Failed to rebalance config panel", exc_info=True)


def _bind_autosave_field_events(page: Any) -> None:
    """Wire generic field-change signals to the autosave decorator entry.

    This helper connects common widget signals (textChanged, toggled,
    valueChanged, currentIndexChanged) for all widgets registered in
    ``page.field_widgets`` to the unified :func:`handle_config_event`
    dispatcher using a lightweight ``field_changed`` event.  The actual
    persistence work is performed by the :func:`autosave_config`
    decorator in ``src.ui.model.autosave``.

    Only edits that occur while the page is *not* in a refresh pass
    (``page._refreshing``) will trigger autosave, so rule-driven
    programmatic updates do not cause redundant writes.
    """
    if getattr(page, "_autosave_bound", False):
        return
    setattr(page, "_autosave_bound", True)

    field_widgets = getattr(page, "field_widgets", {}) or {}

    # Local imports avoid hard dependencies at module import time.
    try:
        from src.ui.view.common import RfStepSegmentsWidget
    except Exception:  # pragma: no cover - defensive: widget not available
        RfStepSegmentsWidget = None  # type: ignore[assignment]
    try:
        # Optional composite widget used by test_switch_wifi.
        from src.ui.view.config.config_switch_wifi import SwitchWifiConfigPage
    except Exception:  # pragma: no cover - optional widget
        SwitchWifiConfigPage = None  # type: ignore[assignment]
    try:
        from src.ui.view.config.config_switch_wifi import SwitchWifiConfigPage
    except Exception:  # pragma: no cover - optional widget
        SwitchWifiConfigPage = None  # type: ignore[assignment]

    for field_key, widget in field_widgets.items():
        if widget is None:
            continue

        def _make_handler(key: str):
            def _on_changed(*_args: Any) -> None:
                # Skip autosave while the page is performing a refresh so
                # that rule-driven widget updates do not cause spurious
                # config writes.
                if getattr(page, "_refreshing", False):
                    return
                handle_config_event(page, "field_changed", field=key)

            return _on_changed

        handler = _make_handler(field_key)

        # Custom composite widgets: wire their internal edits/buttons.
        if RfStepSegmentsWidget is not None and isinstance(widget, RfStepSegmentsWidget):
            for attr in ("start_edit", "stop_edit", "step_edit"):
                edit = getattr(widget, attr, None)
                if edit is not None and hasattr(edit, "textChanged"):
                    edit.textChanged.connect(handler)
            for attr in ("add_btn", "del_btn"):
                btn = getattr(widget, attr, None)
                if btn is not None and hasattr(btn, "clicked"):
                    btn.clicked.connect(handler)
            seg_list = getattr(widget, "segment_list", None)
            if seg_list is not None and hasattr(seg_list, "currentRowChanged"):
                seg_list.currentRowChanged.connect(handler)
            continue
        # SwitchWifiConfigPage: treat entriesChanged as a field-change event so
        # that manual Wi‑Fi edits participate in autosave.
        if SwitchWifiConfigPage is not None and isinstance(widget, SwitchWifiConfigPage):
            if hasattr(widget, "entriesChanged"):
                widget.entriesChanged.connect(handler)
            continue
        # SwitchWifiConfigPage: treat entriesChanged as a "field_changed"
        # signal so that manual Wi-Fi edits participate in autosave.
        if SwitchWifiConfigPage is not None and isinstance(widget, SwitchWifiConfigPage):
            if hasattr(widget, "entriesChanged"):
                widget.entriesChanged.connect(handler)
            continue

        # QFluent ComboBox: connect both index and text change signals so
        # autosave is triggered regardless of which signal the widget emits.
        try:
            from qfluentwidgets import ComboBox as FluentComboBox  # type: ignore
        except Exception:  # pragma: no cover - defensive
            FluentComboBox = None  # type: ignore[assignment]
        if FluentComboBox is not None and isinstance(widget, FluentComboBox):
            if hasattr(widget, "currentIndexChanged"):
                widget.currentIndexChanged.connect(handler)
            if hasattr(widget, "currentTextChanged"):
                widget.currentTextChanged.connect(handler)
            continue

        # Standard widgets: prefer high-level change notifications.
        if hasattr(widget, "toggled"):
            widget.toggled.connect(handler)
            continue
        if hasattr(widget, "currentIndexChanged"):
            widget.currentIndexChanged.connect(handler)
            continue
        if hasattr(widget, "valueChanged") and not hasattr(widget, "currentText"):
            widget.valueChanged.connect(handler)
            continue
        if hasattr(widget, "textChanged"):
            widget.textChanged.connect(handler)
            continue


@autosave_config
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
        # Initial UI pass: derive state from current config and widget values
        # and apply testcase + simple rules once.
        try:
            case_path = getattr(page, "_current_case_path", "") or ""
        except Exception:
            case_path = ""
        apply_ui(page, case_path)
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
        if display_path:
            setattr(page, "_current_case_display_path", display_path)

        # Update "Selected Test Case" text if such a field exists.
        field_widgets = getattr(page, "field_widgets", {}) or {}
        updated_widgets: set[int] = set()
        text_value = display_path or case_path
        for key, widget in field_widgets.items():
            if key == "text_case" or key.endswith(".text_case"):
                if widget is None or id(widget) in updated_widgets:
                    continue
                if hasattr(widget, "setText"):
                    try:
                        widget.setText(text_value)
                        updated_widgets.add(id(widget))
                    except Exception:
                        continue
        if not updated_widgets:
            # Use centralized display updater for the selected test case.
            try:
                update_test_case_display(page, text_value)
            except Exception:
                logging.debug("update_test_case_display failed in case_clicked", exc_info=True)

        # Re-compute testcase-specific UI and apply rules.
        view = getattr(page, "view", None)
        if config_ctl is not None:
            apply_ui(page, case_path)
            if view is not None and hasattr(view, "set_current_page"):
                try:
                    if config_ctl.is_stability_case(case_path):
                        view.set_current_page("stability")
                    elif config_ctl.is_performance_case(case_path):
                        view.set_current_page("execution")
                except Exception as exc:
                    logging.debug("auto page switch failed: %s", exc)
        # Compose DUT Settings according to the testcase category so that
        # category-specific settings (such as Compatibility Settings) are
        # only visible when relevant.
        try:
            from pathlib import Path as _Path

            normalized_display = _Path(display_path).as_posix() if display_path else ""
            apply_dut_settings_for_case(page, case_path=case_path, display_path=normalized_display)
        except Exception:
            logging.debug("case_clicked: apply_dut_settings_for_case failed", exc_info=True)
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
        try:
            evaluate_all_rules(page, "serial_port.status")
        except Exception:
            pass
        return

    if event == "rf_model_changed":
        # RF model changes are now handled by the simple rule engine.
        # The event is kept only to allow panel rebalancing when the set of
        # visible RF fields changes.
        if hasattr(page, "_execution_panel"):
            _rebalance_panel(page._execution_panel)
        return

    if event == "rvr_tool_changed":
        tool_text = str(payload.get("tool_text", ""))
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

    if event == "field_changed":
        # Generic field-change events are used purely to drive the
        # autosave decorator; no additional view behaviour is required.
        field = payload.get("field")
        try:
            if isinstance(field, str) and field.startswith("compatibility."):
                # Defer refresh so autosave can flush widget state first.
                QTimer.singleShot(0, lambda: _refresh_case_page_compatibility(page))
        except Exception:
            logging.debug("compatibility refresh scheduling failed", exc_info=True)
        return

    if event in {
        "stability_exitfirst_changed",
        "stability_ping_changed",
        "stability_script_section_toggled",
        "stability_relay_type_changed",
        "switch_wifi_use_router_changed",
        "switch_wifi_router_csv_changed",
    }:
        # Stability Settings: test_str / test_switch_wifi duration & relay
        # rules. All concrete enable/disable behaviour is defined via simple
        # rules in CUSTOM_SIMPLE_UI_RULES; here we re-evaluate them based on
        # updated widget states.
        try:
            evaluate_all_rules(page, None)
        except Exception:
            pass
        return

    # Unknown events are ignored to keep the dispatcher tolerant of future
    # extensions.
    logging.debug("handle_config_event: unknown event %r payload=%r", event, payload)


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

    # Ensure compatibility section exists with basic structure so that the
    # Compatibility Settings panel can bind fields without special cases.
    if "compatibility" not in config or not isinstance(config["compatibility"], dict):
        config["compatibility"] = {}

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
        config["project"] = config_ctl.normalize_project_section(config.get("project"))

    if config_ctl is not None:
        config["stability"] = config_ctl.normalize_stability_settings(
            config.get("stability")
        )

    # Build panels from YAML schemas.  Parent all groups directly
    # to the corresponding ConfigGroupPanel so that layout is fully
    # owned by the view layer.
    dut_schema = load_ui_schema("dut")
    dut_panel = getattr(page, "_dut_panel", None)
    build_groups_from_schema(page, config, dut_schema, panel_key="dut", parent=dut_panel)

    # Compatibility Settings live on their own panel so that they can
    # behave as a dedicated Settings tab for compatibility testcases.
    compat_schema = load_ui_schema("compatibility")
    if compat_schema:
        compat_panel = getattr(page, "_compatibility_panel", None)
        build_groups_from_schema(page, config, compat_schema, panel_key="compatibility", parent=compat_panel)
        # Enrich the Compatibility Settings group with a composite relay editor
        # and populate NIC choices dynamically.
        try:
            from src.ui.view.config.config_compatibility import CompatibilityRelayEditor

            other_groups = getattr(page, "_other_groups", {}) or {}
            compat_group = other_groups.get("compatibility_settings")
            if isinstance(compat_group, QWidget):
                from PyQt5.QtWidgets import QFormLayout

                layout = compat_group.layout()
                if not isinstance(layout, QFormLayout):
                    layout = QFormLayout(compat_group)
                    compat_group.setLayout(layout)

                # NIC combo comes from the UI schema (compatibility.nic).
                field_widgets = getattr(page, "field_widgets", {}) or {}
                nic_combo = field_widgets.get("compatibility.nic")

                # Collect local NIC labels.
                nic_labels: list[str] = []
                try:
                    import psutil  # type: ignore

                    for name, addrs in psutil.net_if_addrs().items():
                        # Skip loopback-only interfaces.
                        has_non_loopback = any(
                            getattr(addr, "address", "").strip() not in ("127.0.0.1", "")
                            for addr in addrs
                        )
                        if has_non_loopback:
                            nic_labels.append(str(name))
                except Exception:
                    nic_labels = []

                if isinstance(nic_combo, ComboBox):
                    current_value = getattr(page.config.get("compatibility", {}), "get", lambda _k, _d=None: None)(
                        "nic", ""
                    )
                    nic_combo.clear()
                    for label in nic_labels:
                        nic_combo.addItem(label)
                    if current_value:
                        nic_combo.setCurrentText(str(current_value))

                # Insert relay editor under the NIC row.
                relay_editor = CompatibilityRelayEditor(compat_group)
                layout.addRow("Power relays", relay_editor)

                # Initialise from config if available.
                compat_cfg = config.get("compatibility", {}) or {}
                power_cfg = compat_cfg.get("power_ctrl", {}) or {}
                relays = power_cfg.get("relays") or []
                relay_editor.set_relays(relays)

                # Expose for sync_widgets_to_config and autosave.
                field_widgets["compatibility.power_ctrl.relays"] = relay_editor

                def _on_relays_changed() -> None:
                    handle_config_event(page, "field_changed", field="compatibility.power_ctrl.relays")

                relay_editor.entriesChanged.connect(_on_relays_changed)
        except Exception:
            logging.debug("Failed to initialise Compatibility relay editor", exc_info=True)

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
    # Serial / RF / RvR / router field wiring is now driven by the
    # declarative view-event table via ``bind_view_events``.
    _bind_turntable_actions(page)
    _bind_case_tree_actions(page)
    _bind_csv_actions(page)
    _bind_run_actions(page)

    # Bind declarative view events for the Config page.
    try:
        bind_view_events(page, "config", handle_config_event)
    except Exception:
        logging.debug("bind_view_events(config) failed", exc_info=True)

    # Finally, attach generic autosave wiring so that any widget edit on
    # the Config page is persisted via the unified decorator-based flow.
    _bind_autosave_field_events(page)


def set_available_pages(page: Any, page_keys: list[str]) -> None:
    """Delegate logical page selection to the Config page implementation."""
    if hasattr(page, "set_available_pages"):
        page.set_available_pages(page_keys)


def apply_config_ui_rules(page: Any) -> None:
    """Compatibility wrapper around the unified rule engine.

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
    """Wire Android/System version combo to existing mapping logic."""
    field_widgets = getattr(page, "field_widgets", {}) or {}

    version_widget = field_widgets.get("system.version")
    kernel_widget = field_widgets.get("system.kernel_version")
    if version_widget is None or kernel_widget is None:
        return

    setattr(page, "android_version_combo", version_widget)
    setattr(page, "kernel_version_combo", kernel_widget)

    # Reconnect Android Version combo to the original handler, but keep
    # the kernel combo's enabled state controlled purely by connect_type
    # and the rule engine.
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

    # Initial population based on persisted project configuration so that
    # the first display matches YAML values.
    config = getattr(view, "config", {}) or {}
    project_cfg = config.get("project") or {}

    target_customer = str(project_cfg.get("customer") or customer_combo.currentText() or "").strip()
    if target_customer:
        customer_combo.setCurrentText(target_customer)
    refresh_fpga_product_lines(view, target_customer)

    target_product = str(project_cfg.get("product_line") or product_combo.currentText() or "").strip()
    if target_product:
        product_combo.setCurrentText(target_product)
    refresh_fpga_projects(view, target_customer, target_product)

    target_project = str(project_cfg.get("project") or project_combo.currentText() or "").strip()
    if target_project:
        project_combo.setCurrentText(target_project)

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
        config["project"] = dict(normalized)

    field_widgets = getattr(page, "field_widgets", {}) or {}
    for key, field_key in (
        ("main_chip", "project.main_chip"),
        ("wifi_module", "project.wifi_module"),
        ("interface", "project.interface"),
    ):
        widget = field_widgets.get(field_key)
        if widget is not None and hasattr(widget, "setText"):
            widget.setText(normalized.get(key, "") or "")


def apply_connect_type_ui_state(page: Any, connect_type: str) -> None:
    """Control-type UI hook placeholder.

    All field-level attribute changes (Android vs Linux device/IP fields and
    related system widgets) are expressed via the simple rule engine in
    ``rules.py``.  This helper no longer mutates widget attributes directly
    so that the DUT section stays purely rule-driven.
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

    if hasattr(page, "_dut_panel"):
        _rebalance_panel(page._dut_panel)

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


def _bind_serial_actions(page: Any) -> None:
    """Serial wiring is handled by the view-event table."""
    _ = page


def _bind_rf_rvr_actions(page: Any) -> None:
    """RF / RvR wiring is handled by the view-event table."""
    _ = page


def _bind_turntable_actions(page: Any) -> None:
    """Turntable field behaviour is driven by the simple rule engine.

    The generic simple-rule wiring in :class:`CaseConfigPage` connects the
    ``Turntable.model`` combo to the rule engine, so no extra per-field
    wiring is required here.  This function is kept as a placeholder to
    avoid breaking the refresh pipeline.
    """
    return


def _bind_router_actions(page: Any) -> None:
    """Router wiring is handled by the view-event table."""
    _ = page


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
        # Prefer controller run handler; fall back to page.config_ctl when
        # controller reference is present on the page (legacy compatibility).
        if config_ctl is not None and hasattr(config_ctl, "on_run"):
            btn.clicked.connect(lambda _checked=False, ctl=config_ctl: ctl.on_run())
        elif hasattr(page, "config_ctl") and getattr(page, "config_ctl") is not None and hasattr(page.config_ctl, "on_run"):
            btn.clicked.connect(lambda _checked=False, ctl=page.config_ctl: ctl.on_run())


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
