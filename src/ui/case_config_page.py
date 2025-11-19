from __future__ import annotations

import copy
import os
import re
from pathlib import Path
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence
from typing import Annotated
import sip
from src.tools.router_tool.router_factory import router_list, get_router
from src.util.constants import (
    ANDROID_KERNEL_MAP,
    DEFAULT_ANDROID_VERSION_CHOICES,
    DEFAULT_KERNEL_VERSION_CHOICES,
    DEFAULT_RF_STEP_SPEC,
    FONT_FAMILY,
    AUTH_OPTIONS,
    RouterConst,
    TEXT_COLOR,
    WIFI_PRODUCT_PROJECT_MAP,
    get_config_base,
    get_src_base,
    TOOL_SECTION_KEY,
    SWITCH_WIFI_CASE_KEY,
    SWITCH_WIFI_CASE_ALIASES,
    SWITCH_WIFI_CASE_KEYS,
    SWITCH_WIFI_USE_ROUTER_FIELD,
    SWITCH_WIFI_ROUTER_CSV_FIELD,
    SWITCH_WIFI_MANUAL_ENTRIES_FIELD,
    SWITCH_WIFI_ENTRY_SSID_FIELD,
    SWITCH_WIFI_ENTRY_SECURITY_FIELD,
    SWITCH_WIFI_ENTRY_PASSWORD_FIELD,
    TURN_TABLE_SECTION_KEY,
    TURN_TABLE_FIELD_MODEL,
    TURN_TABLE_FIELD_IP_ADDRESS,
    TURN_TABLE_FIELD_STEP,
    TURN_TABLE_FIELD_STATIC_DB,
    TURN_TABLE_FIELD_TARGET_RSSI,
    TURN_TABLE_MODEL_CHOICES,
    TURN_TABLE_MODEL_RS232,
    TURN_TABLE_MODEL_OTHER,
)
from src.tools.config_loader import load_config, save_config
from PyQt5.QtCore import (
    Qt,
    QSignalBlocker,
    QTimer,
    QEasingCurve,
    QDir,
    QSortFilterProxyModel,
    QModelIndex,
    QPropertyAnimation,
    QPoint,
    QRect,
    QRegularExpression,
    pyqtSignal,
    QEvent,
    QObject,
)
from PyQt5.QtGui import QIntValidator, QRegularExpressionValidator, QFont

from PyQt5.QtWidgets import (
    QSizePolicy,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QFileSystemModel,
    QCheckBox,
    QSplitter,
    QStackedWidget,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QDoubleSpinBox,
    QFormLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)

from qfluentwidgets import (
    CardWidget,
    LineEdit,
    PushButton,
    ComboBox,
    FluentIcon,
    TextEdit,
    InfoBar,
    InfoBarPosition,
    ScrollArea
)

try:
    from qfluentwidgets import StepView  # type: ignore
except Exception:  # pragma: no cover - fall back to custom indicator when runtime is missing
    StepView = None
from .view.common import (
    AnimatedTreeView,
    ConfigGroupPanel,
    EditableInfo,
    ScriptConfigEntry,
    PAGE_CONTENT_MARGIN,
    GROUP_COLUMN_SPACING,
    GROUP_ROW_SPACING,
    STEP_LABEL_SPACING,
    USE_QFLUENT_STEP_VIEW,
    _apply_step_font,
    attach_view_to_page,
)
from .view.common import TestFileFilterModel, _StepSwitcher
from .view.config import RfStepSegmentsWidget, SwitchWifiManualEditor
from src.ui.view.config.actions import (
    apply_rf_model_ui_state,
    apply_run_lock_ui_state,
    apply_rvr_tool_ui_state,
    apply_serial_enabled_ui_state,
    apply_turntable_model_ui_state,
    refresh_config_page_controls,
    update_fpga_hidden_fields,
    apply_connect_type_ui_state,
    apply_third_party_ui_state,
    handle_third_party_toggled_with_permission,
    apply_field_effects,
    apply_config_ui_rules,
    compute_editable_info,
    update_script_config_ui,
)
from src.ui.view.config.config_str import bind_script_section
from .controller.config_ctl import ConfigController
from .view.builder import load_ui_schema, build_groups_from_schema
from .rvrwifi_proxy import (
    _normalize_switch_wifi_manual_entries as _proxy_normalize_switch_wifi_manual_entries,
    _register_switch_wifi_csv_combo as _proxy_register_switch_wifi_csv_combo,
    _unregister_switch_wifi_csv_combo as _proxy_unregister_switch_wifi_csv_combo,
    _list_available_csv_files as _proxy_list_available_csv_files,
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
from src.ui.view.theme import (
    apply_theme,
    apply_font_and_selection,
    apply_groupbox_style,
    CASE_TREE_FONT_SIZE_PX,
    STEP_LABEL_FONT_PIXEL_SIZE,
    SWITCH_WIFI_TABLE_HEADER_BG,
    SWITCH_WIFI_TABLE_HEADER_FG,
    SWITCH_WIFI_TABLE_SELECTION_BG,
    SWITCH_WIFI_TABLE_SELECTION_FG,
)
from .model.rules import CONFIG_UI_RULES, FieldEffect, RuleSpec, SIDEBAR_RULES


class CaseConfigPage(CardWidget):
    """
    The primary user interface for browsing and configuring test cases prior
    to execution.

    This page combines a tree view of available test scripts, a set of dynamic
    configuration panels for the selected script, and controls for loading
    router information, editing Wi‑Fi credentials, adjusting durations and
    checkpoints, and launching the test run.  The page holds references to
    numerous widgets, tracks application state (like the currently loaded
    configuration and router object), and manages persistence via loading and
    saving of a JSON configuration file.
    """

    routerInfoChanged = pyqtSignal()
    csvFileChanged = pyqtSignal(str)

    def on_run(self) -> None:
        """Entry point used by RunPage and other callers to start a run via controller."""
        if getattr(self, "config_ctl", None) is not None:
            self.config_ctl.on_run()

    def __init__(self, on_run_callback):
        """
        Initialize the class instance, set up initial state and construct UI widgets.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        super().__init__()
        self.setObjectName("caseConfigPage")
        self.on_run_callback = on_run_callback
        apply_theme(self)
        self.selected_csv_path: str | None = None
        # Controller responsible for config lifecycle/normalisation.
        self.config_ctl = ConfigController(self)
        # Load the persisted tool configuration and restore CSV selection.
        self.config: dict = self.config_ctl.load_initial_config()
        # Initialize transient state flags used by the UI during refreshes and selections
        self._refreshing = False
        self._pending_path: str | None = None
        # Mapping from config field keys (e.g. "android_system.version") to widgets
        self.field_widgets: dict[str, QWidget] = {}
        # Mapping from logical UI identifiers (config_panel_group_field_type) to widgets
        self.config_controls: dict[str, QWidget] = {}
        self._duration_control_group: QGroupBox | None = None
        self._check_point_group: QGroupBox | None = None
        self.router_obj = None
        self._enable_rvr_wifi: bool = False
        self._router_config_active: bool = False
        self._run_locked: bool = False
        self._locked_fields: set[str] | None = None
        self._current_case_path: str = ""
        self._last_editable_info: EditableInfo | None = None
        self._switch_wifi_csv_combos: list[ComboBox] = []

        # Delegate view construction to ConfigView for layout/structure.
        from .view.config import ConfigView

        self._android_versions = list(DEFAULT_ANDROID_VERSION_CHOICES)
        self._kernel_versions = list(DEFAULT_KERNEL_VERSION_CHOICES)

        # Compose pure UI view and attach it to this page.
        self.view = ConfigView(self)
        attach_view_to_page(self, self.view)
        self.splitter = self.view.splitter
        self.case_tree = self.view.case_tree
        self.scroll_area = self.view.scroll_area
        self.stack = self.view.stack
        self._page_panels = self.view._page_panels
        self._page_widgets = self.view._page_widgets
        self._run_buttons = self.view._run_buttons
        self._dut_panel = self._page_panels["dut"]
        self._execution_panel = self._page_panels["execution"]
        self._stability_panel = self._page_panels["stability"]
        # Track logical pages from the controller perspective (used by rules/business logic).
        self._current_page_keys: list[str] = ["dut"]
        self._script_config_factories: dict[str, Callable[[str, str, Mapping[str, Any]], ScriptConfigEntry]] = {
            "test/stability/test_str.py": self._create_test_str_config_entry_from_schema,
            "test/stability/test_switch_wifi.py": self._create_test_swtich_wifi_config_entry_from_schema,
        }
        self._script_groups: dict[str, ScriptConfigEntry] = {}
        self._active_script_case: str | None = None
        self._config_panels = tuple(self._page_panels[key] for key in ("dut", "execution", "stability"))
        self._sync_run_buttons_enabled()
        # render form fields from yaml（委托给 view/config/actions.refresh_config_page_controls）
        self._dut_groups: dict[str, QWidget] = {}
        self._other_groups: dict[str, QWidget] = {}
        refresh_config_page_controls(self)
        self._initialize_script_config_groups()
        self._build_wizard_pages()
        # initialise case tree using src/test as root (non-fatal on failure)
        try:
            base = Path(self._get_application_base())
            test_root = base / "test"
            if test_root.exists():
                self._init_case_tree(test_root)
        except Exception:
            pass
        self._refresh_script_section_states()
        self._request_rebalance_for_panels()
        self.routerInfoChanged.connect(self._update_csv_options)
        self._update_csv_options()
        # connect signals AFTER UI ready
        self.case_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        QTimer.singleShot(0, lambda: self.get_editable_fields(""))

    def resizeEvent(self, event):
        """
        Execute the resizeEvent routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        super().resizeEvent(event)
        self.splitter.setSizes([int(self.width() * 0.2), int(self.width() * 0.8)])

    def _navigate_to_index(self, target_index: int) -> None:
        """
        Execute the navigate to index routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if self.stack.count() == 0:
            return
        target_index = max(0, min(target_index, self.stack.count() - 1))
        current = self.stack.currentIndex()
        if target_index == current:
            return
        if current == 0 and target_index > current and not self._validate_first_page():
            self.stack.setCurrentIndex(0)
            return
        if getattr(self, "config_ctl", None) is not None:
            self.config_ctl.sync_widgets_to_config()
        self.stack.setCurrentIndex(target_index)

    def _sync_run_buttons_enabled(self) -> None:
        """
        Execute the sync run buttons enabled routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if getattr(self, "config_ctl", None) is not None:
            self.config_ctl.sync_run_buttons_enabled()

    def _request_rebalance_for_panels(self, *panels: ConfigGroupPanel) -> None:
        """
        Execute the request rebalance for panels routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        targets = panels or self._config_panels
        for panel in targets:
            panel.request_rebalance()

    def _build_wizard_pages(self) -> None:
        """
        Execute the build wizard pages routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self._dut_panel.set_groups(list(self._dut_groups.values()))
        self._execution_panel.set_groups(self._compose_other_groups())

    def _compose_other_groups(self) -> list[QWidget]:
        """
        Combine non-DUT groups for the Execution Settings panel.

        Only generic execution groups (turntable / RF / RvR / debug ...)
        should appear here. Stability-only groups such as Duration Control,
        Check Point and per-script stability case groups belong to the
        Stability Settings panel and are filtered out.
        """
        groups: list[QWidget] = []
        for key, group in self._other_groups.items():
            # Skip stability panel sections which are rendered separately.
            if key in {"duration_control", "check_point"}:
                continue
            if key.startswith("cases."):
                continue
            groups.append(group)
        return groups

    def _list_serial_ports(self) -> list[tuple[str, str]]:
        """
        Execute the list serial ports routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        ports: list[tuple[str, str]] = []
        try:
            from serial.tools import list_ports  # type: ignore
        except Exception:
            logging.debug("serial.tools.list_ports unavailable", exc_info=True)
            return ports
        try:
            for info in list_ports.comports():
                label = info.device
                description = getattr(info, "description", "") or ""
                if description and description != info.device:
                    label = f"{info.device} ({description})"
                ports.append((info.device, label))
        except Exception as exc:
            logging.debug("Failed to enumerate serial ports: %s", exc)
            return []
        return ports

    def _set_available_pages(self, page_keys: Sequence[str]) -> None:
        """
        Set the available pages property on the instance.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        normalized: list[str] = []
        for key in page_keys:
            if key not in self._page_widgets:
                continue
            if key not in normalized:
                normalized.append(key)
        if "dut" not in normalized:
            normalized.insert(0, "dut")
        # Record logical state for rules/business logic (always update).
        self._current_page_keys = normalized
        # Delegate page visibility to the view.
        self.view.set_available_pages(normalized)

    def _determine_pages_for_case(self, case_path: str, info: EditableInfo) -> list[str]:
        """Delegate page-key computation to the config controller."""
        return self.config_ctl.determine_pages_for_case(case_path, info)

    def _script_case_key(self, case_path: str | Path) -> str:
        """Return the script key using controller helper so rules stay in sync."""
        return self.config_ctl.script_case_key(case_path)

    def _script_field_key(self, case_key: str, *parts: str) -> str:
        """
        Execute the script field key routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        suffix = ".".join(parts)
        return f"stability.cases.{case_key}.{suffix}"

    def _initialize_script_config_groups(self) -> None:
        """
        Execute the initialize script config groups routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        stability_cfg = self.config.setdefault("stability", {})
        stability_cfg.setdefault("cases", {})
        self._script_groups.clear()
        for case_path, factory in self._script_config_factories.items():
            case_key = self._script_case_key(case_path)
            # Ensure config defaults for this stability script via controller.
            entry_config = self.config_ctl.ensure_script_case_defaults(case_key, case_path)
            entry = factory(case_key, case_path, entry_config)
            entry.group.setVisible(False)
            self._script_groups[case_key] = entry
            self.field_widgets.update(entry.widgets)
        self._stability_panel.set_groups(self._compose_stability_groups(None))

    @staticmethod
    def _normalize_switch_wifi_manual_entries(entries: Any) -> list[dict[str, str]]:
        """Proxy to normalise manual Wi-Fi entries for switch Wi-Fi cases."""
        return _proxy_normalize_switch_wifi_manual_entries(entries)

    def _load_script_config_into_widgets(
            self,
            entry: ScriptConfigEntry,
            data: Mapping[str, Any] | None,
    ) -> None:
        """
        Load  script config into widgets from persistent storage into memory.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        data = data or {}
        case_key = entry.case_key

        if case_key == SWITCH_WIFI_CASE_KEY:
            use_router_widget = entry.widgets.get(
                self._script_field_key(case_key, SWITCH_WIFI_USE_ROUTER_FIELD)
            )
            router_combo = entry.widgets.get(
                self._script_field_key(case_key, SWITCH_WIFI_ROUTER_CSV_FIELD)
            )
            manual_widget = entry.widgets.get(
                self._script_field_key(case_key, SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
            )
            use_router_value = bool(data.get(SWITCH_WIFI_USE_ROUTER_FIELD))
            if isinstance(use_router_widget, QCheckBox):
                use_router_widget.setChecked(use_router_value)
            router_path = self._resolve_csv_config_path(
                data.get(SWITCH_WIFI_ROUTER_CSV_FIELD)
            )
            if isinstance(router_combo, ComboBox):
                include_placeholder = router_combo.property("switch_wifi_include_placeholder")
                use_placeholder = True if include_placeholder is None else bool(include_placeholder)
                self._populate_csv_combo(router_combo, router_path, include_placeholder=use_placeholder)
                try:
                    self._set_selected_csv(router_path, sync_combo=True)
                except Exception:
                    logging.debug(
                        "Failed to sync selected CSV for switch_wifi defaults",
                        exc_info=True,
                    )
                signal = getattr(self, "csvFileChanged", None)
                if signal is not None and hasattr(signal, "emit"):
                    try:
                        signal.emit(router_path or "")
                    except Exception:
                        logging.debug(
                            "Failed to emit csvFileChanged for switch_wifi defaults",
                            exc_info=True,
                        )
                # 保证 Execution Settings / RvR Wi‑Fi 使用的 CSV 选择
                # 与 switch_wifi router_csv 的默认值保持一致，这样
                # 初次打开时两个下拉框指向同一个文件。
                try:
                    self._set_selected_csv(router_path, sync_combo=True)
                except Exception:
                    logging.debug("Failed to sync selected_csv_path from switch_wifi defaults", exc_info=True)
            if isinstance(manual_widget, SwitchWifiManualEditor):
                manual_entries = data.get(SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
                if isinstance(manual_entries, Sequence) and not isinstance(manual_entries, (str, bytes)):
                    manual_widget.set_entries(manual_entries)
                else:
                    manual_widget.set_entries(None)
            # router_preview / apply_mode are deprecated; preview is removed
            # and router/manual mode is handled by view/actions layer.
            return

        ac_cfg = data.get("ac", {})
        str_cfg = data.get("str", {})

        def _set_spin(key: str, raw_value: Any) -> None:
            """
            Set a numeric duration field (AC/STR on/off) from stored value.

            Historically these were QSpinBox widgets; schema has been updated
            to use line edits, so this helper now supports both QSpinBox and
            LineEdit while keeping the numeric normalisation in one place.
            """
            widget = entry.widgets.get(key)
            try:
                value = int(raw_value)
            except (TypeError, ValueError):
                value = 0
            value = max(0, value)
            if isinstance(widget, QSpinBox):
                with QSignalBlocker(widget):
                    widget.setValue(value)
            elif isinstance(widget, LineEdit):
                with QSignalBlocker(widget):
                    widget.setText(str(value))

        def _set_checkbox(key: str, raw_value: Any) -> None:
            """
            Set the checkbox property on the instance.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            widget = entry.widgets.get(key)
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(raw_value))

        def _set_combo(key: str, raw_value: Any) -> None:
            """
            Set the combo property on the instance.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            widget = entry.widgets.get(key)
            if not isinstance(widget, ComboBox):
                return
            value = str(raw_value or "").strip()
            with QSignalBlocker(widget):
                if value:
                    index = widget.findData(value)
                    if index < 0:
                        index = next(
                            (i for i in range(widget.count()) if widget.itemText(i) == value),
                            -1,
                        )
                    if index < 0:
                        widget.addItem(value, value)
                        index = widget.findData(value)
                    widget.setCurrentIndex(index if index >= 0 else max(widget.count() - 1, 0))
                else:
                    widget.setCurrentIndex(0 if widget.count() else -1)

        _set_checkbox(self._script_field_key(case_key, "ac", "enabled"), ac_cfg.get("enabled"))
        _set_spin(self._script_field_key(case_key, "ac", "on_duration"), ac_cfg.get("on_duration"))
        _set_spin(self._script_field_key(case_key, "ac", "off_duration"), ac_cfg.get("off_duration"))
        _set_combo(self._script_field_key(case_key, "ac", "port"), ac_cfg.get("port"))
        _set_combo(self._script_field_key(case_key, "ac", "mode"), ac_cfg.get("mode"))

        _set_checkbox(self._script_field_key(case_key, "str", "enabled"), str_cfg.get("enabled"))
        _set_spin(self._script_field_key(case_key, "str", "on_duration"), str_cfg.get("on_duration"))
        _set_spin(self._script_field_key(case_key, "str", "off_duration"), str_cfg.get("off_duration"))
        _set_combo(self._script_field_key(case_key, "str", "port"), str_cfg.get("port"))
        _set_combo(self._script_field_key(case_key, "str", "mode"), str_cfg.get("mode"))

    def _refresh_script_section_states(self) -> None:
        """
        Refresh script section state using the rule engine.
        """
        apply_config_ui_rules(self)

    def _create_test_swtich_wifi_config_entry_from_schema(
            self,
            case_key: str,
            case_path: str,
            data: Mapping[str, Any],
    ) -> ScriptConfigEntry:
        """
        Build ScriptConfigEntry for ``test_switch_wifi`` using widgets created
        by the YAML/schema builder.

        No new groups are created here; the builder is responsible for the
        visual layout. This helper only wires logical field keys so that
        rules and config loading can operate uniformly.
        """
        section_id = f"cases.{case_key}"
        group = self._other_groups.get(section_id)
        if group is None:
            group = QWidget(self)

        widgets: dict[str, QWidget] = {}

        def _bind_field(field: str) -> QWidget | None:
            script_key = self._script_field_key(case_key, field)
            widget = self.field_widgets.get(script_key)
            if widget is None:
                raw_key = f"{section_id}.{field}"
                widget = self.field_widgets.get(raw_key)
                if widget is not None:
                    self.field_widgets[script_key] = widget
            if widget is not None:
                widgets[script_key] = widget
            return widget

        use_router_widget = _bind_field(SWITCH_WIFI_USE_ROUTER_FIELD)
        router_widget = _bind_field(SWITCH_WIFI_ROUTER_CSV_FIELD)
        manual_widget = _bind_field(SWITCH_WIFI_MANUAL_ENTRIES_FIELD)

        # When the schema provides a widget for manual entries, replace that
        # single field with the dedicated SwitchWifiManualEditor and fan out
        # its controls into separate form rows so that the layout matches
        # other fields (label on the left, editor on the right).
        if isinstance(manual_widget, QWidget):
            parent = manual_widget.parent() or group
            layout = parent.layout()
            try:
                if isinstance(layout, QFormLayout):
                    label = layout.labelForField(manual_widget)
                    row = layout.getWidgetPosition(manual_widget)[0]
                    layout.removeWidget(manual_widget)
                    manual_widget.setParent(None)

                    editor = SwitchWifiManualEditor(parent)
                    widgets[self._script_field_key(case_key, SWITCH_WIFI_MANUAL_ENTRIES_FIELD)] = editor
                    manual_widget = editor

                    # Row 1: Wi‑Fi list table.
                    wifi_label = label or QLabel("Wi-Fi list", parent)
                    layout.insertRow(row, wifi_label, editor.table)
                    row += 1
                    # Row 2: SSID field.
                    layout.insertRow(row, QLabel("SSID", parent), editor.ssid_edit)
                    row += 1
                    # Row 3: Security combo.
                    layout.insertRow(row, QLabel("Security", parent), editor.security_combo)
                    row += 1
                    # Row 4: Password field.
                    layout.insertRow(row, QLabel("Password", parent), editor.password_edit)
                    row += 1
                    # Row 5: Add/Remove buttons (no label).
                    buttons_container = QWidget(parent)
                    buttons_layout = QHBoxLayout(buttons_container)
                    buttons_layout.setContentsMargins(0, 0, 0, 0)
                    buttons_layout.setSpacing(8)
                    buttons_layout.addWidget(editor.add_btn)
                    buttons_layout.addWidget(editor.del_btn)
                    buttons_layout.addStretch(1)
                    layout.insertRow(row, QLabel("", parent), buttons_container)
            except Exception:
                pass

        # Treat router_csv as a CSV combo driven by the shared RvR Wi-Fi proxy.
        if isinstance(router_widget, ComboBox):
            self._register_switch_wifi_csv_combo(router_widget)

        field_keys = set(widgets.keys())
        section_controls: dict[str, tuple[QCheckBox, Sequence[QWidget]]] = {}

        return ScriptConfigEntry(
            group=group,
            widgets=widgets,
            field_keys=field_keys,
            section_controls=section_controls,
            case_key=case_key,
            case_path=case_path,
        )

    def _create_test_str_config_entry_from_schema(
            self,
            case_key: str,
            case_path: str,
            data: Mapping[str, Any],
    ) -> ScriptConfigEntry:
        """
        Build ScriptConfigEntry for ``test_str`` using widgets created by the
        YAML/schema builder.

        All AC/STR fields are referenced via ``stability.cases.test_str.*``
        keys (see ui_rules R14/R15). This helper binds those widgets into a
        ScriptConfigEntry and ensures rule evaluation runs when the relevant
        checkboxes or relay-type combos change.
        """
        section_id = f"cases.{case_key}"
        group = self._other_groups.get(section_id)
        if group is None:
            group = QWidget(self)

        widgets: dict[str, QWidget] = {}

        def _bind_field(*parts: str) -> QWidget | None:
            script_key = self._script_field_key(case_key, *parts)
            widget = self.field_widgets.get(script_key)
            if widget is None:
                raw_key = f"{section_id}." + ".".join(parts)
                widget = self.field_widgets.get(raw_key)
                if widget is not None:
                    self.field_widgets[script_key] = widget
            if widget is not None:
                widgets[script_key] = widget
            return widget

        # AC fields
        ac_checkbox = _bind_field("ac", "enabled")
        ac_on = _bind_field("ac", "on_duration")
        ac_off = _bind_field("ac", "off_duration")
        ac_port = _bind_field("ac", "port")
        ac_mode = _bind_field("ac", "mode")
        ac_relay_type = _bind_field("ac", "relay_type")
        ac_relay_params = _bind_field("ac", "relay_params")

        # STR fields
        str_checkbox = _bind_field("str", "enabled")
        str_on = _bind_field("str", "on_duration")
        str_off = _bind_field("str", "off_duration")
        str_port = _bind_field("str", "port")
        str_mode = _bind_field("str", "mode")
        str_relay_type = _bind_field("str", "relay_type")
        str_relay_params = _bind_field("str", "relay_params")

        section_controls: dict[str, tuple[QCheckBox, Sequence[QWidget]]] = {}

        # Bind AC/STR checkboxes so rule engine re-evaluates section state.
        ac_controls: list[QWidget] = [
            w for w in (ac_on, ac_off, ac_port, ac_mode, ac_relay_type, ac_relay_params) if w is not None
        ]
        if isinstance(ac_checkbox, QCheckBox):
            bind_script_section(self, ac_checkbox, ac_controls)
            section_controls["ac"] = (ac_checkbox, tuple(ac_controls))

        str_controls: list[QWidget] = [
            w for w in (str_on, str_off, str_port, str_mode, str_relay_type, str_relay_params) if w is not None
        ]
        if isinstance(str_checkbox, QCheckBox):
            bind_script_section(self, str_checkbox, str_controls)
            section_controls["str"] = (str_checkbox, tuple(str_controls))

        # Ensure relay-type changes also trigger rule evaluation (R15a/b).
        from qfluentwidgets import ComboBox  # local import to avoid cycles

        def _connect_relay_type(widget: QWidget | None) -> None:
            if isinstance(widget, ComboBox):
                widget.currentIndexChanged.connect(lambda *_: apply_config_ui_rules(self))

        _connect_relay_type(ac_relay_type)
        _connect_relay_type(str_relay_type)

        field_keys = set(widgets.keys())

        return ScriptConfigEntry(
            group=group,
            widgets=widgets,
            field_keys=field_keys,
            section_controls=section_controls,
            case_key=case_key,
            case_path=case_path,
        )

        if not case_path:
            return ["dut"]
        keys = ["dut"]
        if self._is_performance_case(case_path) or info.enable_csv:
            keys.append("execution")
        else:
            case_key = self._script_case_key(case_path)
            if case_key in self._script_groups:
                keys.append("stability")
        return keys

    def _register_group(self, key: str, group: QWidget, is_dut: bool) -> None:
        """
        Register a configuration group on the DUT or non‑DUT panel.

        This keeps two internal mappings (``_dut_groups`` and
        ``_other_groups``) used when re‑balancing panel layouts.  The
        function itself does not create widgets; it simply stores
        references passed in from section builders.
        """
        if is_dut:
            self._dut_groups[key] = group
        else:
            self._other_groups[key] = group

    # ------------------------------------------------------------------
    # Logical control identifiers for the Config page
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_control_token(value: str) -> str:
        """Return a lower‑case identifier token derived from ``value``."""
        text = (value or "").strip().lower()
        # Only allow [a‑z0‑9_]; collapse other characters into underscores.
        text = re.sub(r"[^0-9a-z]+", "_", text)
        return text.strip("_") or "x"

    def _widget_suffix(self, widget: QWidget) -> str:
        """Return a short type suffix for ``widget`` (text/combo/check/btn/...)."""
        if isinstance(widget, ComboBox):
            return "combo"
        if isinstance(widget, (LineEdit, TextEdit)):
            return "text"
        if isinstance(widget, QCheckBox):
            return "check"
        if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            return "spin"
        if isinstance(widget, QTableWidget):
            return "table"
        if isinstance(widget, QListWidget):
            return "list"
        if isinstance(widget, QGroupBox):
            return "group"
        if isinstance(widget, PushButton):
            return "btn"
        return "widget"

    def _register_config_control(
        self,
        panel: str,
        group: str,
        field: str,
        widget: QWidget,
    ) -> None:
        """Store a logical identifier for a Config page control.

        The identifier follows the pattern ``config_panel_group_field_type``
        where each token is normalised to lower case and uses underscores
        instead of spaces or punctuation.  This mapping is intended for
        higher‑level schema/automation code and does not affect existing
        field lookups.
        """
        panel_token = self._normalize_control_token(panel or "main")
        group_token = self._normalize_control_token(group or panel or "group")
        field_token = self._normalize_control_token(field or group or "field")
        suffix = self._widget_suffix(widget)
        control_id = f"config_{panel_token}_{group_token}_{field_token}_{suffix}"
        existing = self.config_controls.get(control_id)
        if existing is widget:
            return
        if existing is not None and existing is not widget:
            logging.debug(
                "CaseConfigPage: control id collision for %s (old=%r new=%r)",
                control_id,
                existing,
                widget,
            )
        self.config_controls[control_id] = widget

    def _register_config_control_from_section(
            self,
            section_id: str,
            panel: str,
            field_key: str,
            widget: QWidget,
    ) -> None:
        """Helper used by section classes to register logical control IDs.

        ``field_key`` is typically a dotted path such as
        ``\"android_system.version\"``.  The first component is treated as
        the group name, the last component as the field name.
        """
        if not field_key:
            return
        parts = str(field_key).split(".")
        group = parts[0] if parts else (section_id or "")
        field = parts[-1] if parts else (section_id or field_key)
        self._register_config_control(panel or "main", group, field, widget)

    # ------------------------------------------------------------------
    # Rule evaluation helpers (for CONFIG_UI_RULES)
    # ------------------------------------------------------------------

    def _get_field_value(self, field_key: str) -> Any:
        """Delegate field value lookup to config controller."""
        if getattr(self, "config_ctl", None) is not None:
            return self.config_ctl.get_field_value(field_key)
        return None

    def _apply_field_effects(self, effects: FieldEffect) -> None:
        """Apply enable/disable/show/hide effects to widgets based on a rule."""
        if not effects:
            return
        editable_fields = getattr(getattr(self, "_last_editable_info", None), "fields", None)

        def _set_enabled(key: str, enabled: bool) -> None:
            widget = self.field_widgets.get(key)
            if widget is None:
                return
            # Kernel Version 的可编辑状态由 Control Type 决定：
            # - Android: 始终禁用（值由 Android Version 映射）
            # - Linux:   始终可编辑
            if key == "system.kernel_version":
                connect_type_val = ""
                try:
                    if hasattr(self, "_current_connect_type"):
                        connect_type_val = self._current_connect_type() or ""
                    elif hasattr(self, "connect_type_combo") and hasattr(self.connect_type_combo, "currentText"):
                        connect_type_val = self.connect_type_combo.currentText().strip()
                        if hasattr(self, "_normalize_connect_type_label"):
                            connect_type_val = self._normalize_connect_type_label(connect_type_val)
                except Exception:
                    connect_type_val = ""
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
            widget = self.field_widgets.get(key)
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

    def _eval_case_type_flag(self, flag: str) -> bool:
        """Delegate case-type flag evaluation to config controller."""
        if getattr(self, "config_ctl", None) is not None:
            return self.config_ctl.eval_case_type_flag(flag)
        return True

    def _apply_sidebar_rules(self) -> None:
        """Delegate sidebar rules that depend on the active case to controller."""
        if getattr(self, "config_ctl", None) is not None:
            self.config_ctl.apply_sidebar_rules()

    @staticmethod
    def _is_dut_key(key: str) -> bool:
        """
        Execute the is dut key routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        return key in {
            "connect_type",
            "fpga",
            "serial_port",
            "software_info",
            "hardware_info",
            "android_system",  # legacy
            "system",
        }

    def _refresh_fpga_product_lines(
            self,
            customer: str,
            product_to_select: Optional[str] = None,
            *,
            block_signals: bool = False,
    ) -> None:
        """
        Refresh the  fpga product lines to ensure the UI is up to date.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not hasattr(self, "fpga_product_combo"):
            return
        combo = self.fpga_product_combo
        blocker = QSignalBlocker(combo) if block_signals else None
        customer_upper = customer.strip().upper()
        product_lines = WIFI_PRODUCT_PROJECT_MAP.get(customer_upper, {}) if customer_upper else {}
        combo.clear()
        for product_name in product_lines.keys():
            combo.addItem(product_name)
        if product_to_select and product_to_select in product_lines:
            combo.setCurrentText(product_to_select)
        else:
            combo.setCurrentIndex(-1)
        if blocker is not None:
            del blocker

    def _refresh_fpga_projects(
            self,
            customer: str,
            product_line: str,
            project_to_select: Optional[str] = None,
            *,
            block_signals: bool = False,
    ) -> None:
        """
        Refresh the  fpga projects to ensure the UI is up to date.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not hasattr(self, "fpga_project_combo"):
            return
        combo = self.fpga_project_combo
        blocker = QSignalBlocker(combo) if block_signals else None
        customer_upper = customer.strip().upper()
        product_upper = product_line.strip().upper()
        projects = {}
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
        if project_to_select and project_to_select in projects:
            combo.setCurrentText(project_to_select)
        else:
            combo.setCurrentIndex(-1)
        if blocker is not None:
            del blocker

    def _sync_widgets_to_config(self) -> None:
        """
        Execute the sync widgets to config routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not isinstance(self.config, dict):
            self.config = {}
        if hasattr(self, "_config_tool_snapshot"):
            self.config[TOOL_SECTION_KEY] = copy.deepcopy(
                self._config_tool_snapshot
            )
        for key, widget in self.field_widgets.items():
            parts = key.split('.')
            ref = self.config
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
                    items = [item.strip() for item in val.split(',') if item.strip()]
                    normalized = []
                    for item in items:
                        normalized.append(int(item) if item.isdigit() else item)
                    ref[leaf] = normalized
                    continue
                old_val = ref.get(leaf)
                if isinstance(old_val, list):
                    items = [x.strip() for x in val.split(',') if x.strip()]
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
            elif isinstance(widget, SwitchWifiManualEditor):
                ref[leaf] = widget.serialize()
            elif isinstance(widget, ComboBox):
                data = widget.currentData()
                if data not in (None, "", widget.currentText()):
                    value = data
                else:
                    text = widget.currentText().strip()
                    if text.lower() == 'select port':
                        text = ''
                    value = True if text == 'True' else False if text == 'False' else text
                if key == self._script_field_key(
                        SWITCH_WIFI_CASE_KEY, SWITCH_WIFI_ROUTER_CSV_FIELD
                ):
                    value = self._relativize_config_path(value)
                ref[leaf] = value
            elif isinstance(widget, QSpinBox):
                ref[leaf] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                ref[leaf] = float(widget.value())
            elif isinstance(widget, QCheckBox):
                ref[leaf] = widget.isChecked()
        if hasattr(self, "_fpga_details"):
            self.config["fpga"] = dict(self._fpga_details)
        base = Path(self._get_application_base())
        case_display = self.field_widgets.get("text_case")
        display_text = case_display.text().strip() if isinstance(case_display, LineEdit) else ""
        storage_path = self._current_case_path or self._display_to_case_path(display_text)
        case_path = Path(storage_path).as_posix() if storage_path else ""
        self._current_case_path = case_path
        if case_path:
            abs_case_path = (base / case_path).resolve().as_posix()
        else:
            abs_case_path = ""
        self.config["text_case"] = case_path
        if self.selected_csv_path:
            base_cfg = get_config_base()
            try:
                rel_csv = os.path.relpath(Path(self.selected_csv_path).resolve(), base_cfg)
            except ValueError:
                rel_csv = Path(self.selected_csv_path).resolve().as_posix()
            self.config["csv_path"] = Path(rel_csv).as_posix()
        else:
            self.config.pop("csv_path", None)
        proxy_idx = self.case_tree.currentIndex()
        model = self.case_tree.model()
        src_idx = (
            model.mapToSource(proxy_idx)
            if isinstance(model, QSortFilterProxyModel)
            else proxy_idx
        )
        selected_path = self.fs_model.filePath(src_idx)
        if os.path.isfile(selected_path) and selected_path.endswith(".py"):
            abs_path = Path(selected_path).resolve()
            display_path = os.path.relpath(abs_path, base)
            case_path = Path(display_path).as_posix()
            self._current_case_path = case_path
            self.config["text_case"] = case_path

        stability_cfg = self.config.get("stability")
        if isinstance(stability_cfg, dict):
            duration_cfg = stability_cfg.get("duration_control")
            if isinstance(duration_cfg, dict):
                loop_value = duration_cfg.get("loop")
                if not isinstance(loop_value, int) or loop_value <= 0:
                    duration_cfg["loop"] = None
                duration_value = duration_cfg.get("duration_hours")
                try:
                    duration_float = float(duration_value)
                except (TypeError, ValueError):
                    duration_float = 0.0
                duration_cfg["duration_hours"] = duration_float if duration_float > 0 else None
                duration_cfg["exitfirst"] = bool(duration_cfg.get("exitfirst"))
                try:
                    retry_int = int(duration_cfg.get("retry_limit") or 0)
                except (TypeError, ValueError):
                    retry_int = 0
                duration_cfg["retry_limit"] = max(0, retry_int)
            checkpoint_cfg = stability_cfg.get("check_point")
            if isinstance(checkpoint_cfg, dict):
                checkpoint_cfg["ping"] = bool(checkpoint_cfg.get("ping"))
                checkpoint_cfg["ping_targets"] = str(
                    checkpoint_cfg.get("ping_targets", "") or ""
                ).strip()

    def _validate_first_page(self) -> bool:
        """
        Execute the validate first page routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        errors: list[str] = []
        connect_type = ""
        focus_widget: QWidget | None = None
        if hasattr(self, "connect_type_combo"):
            connect_type = self._current_connect_type()
            if not connect_type:
                errors.append("Connect type is required.")
                focus_widget = focus_widget or self.connect_type_combo
            elif connect_type == "Android" and hasattr(self, "adb_device_edit"):
                if not self.adb_device_edit.text().strip():
                    errors.append("ADB device is required.")
                    focus_widget = focus_widget or self.adb_device_edit
            elif connect_type == "Linux" and hasattr(self, "telnet_ip_edit"):
                if not self.telnet_ip_edit.text().strip():
                    errors.append("Linux IP is required.")
                    focus_widget = focus_widget or self.telnet_ip_edit
                kernel_text = ""
                if hasattr(self, "kernel_version_combo"):
                    kernel_text = self.kernel_version_combo.currentText().strip()
                if not kernel_text:
                    errors.append("Kernel version is required for Linux access.")
                    focus_widget = focus_widget or getattr(self, "kernel_version_combo", None)
            if hasattr(self, "third_party_checkbox") and self.third_party_checkbox.isChecked():
                wait_text = self.third_party_wait_edit.text().strip() if hasattr(self, "third_party_wait_edit") else ""
                if not wait_text or not wait_text.isdigit() or int(wait_text) <= 0:
                    errors.append("Third-party wait time must be a positive integer.")
                    if hasattr(self, "third_party_wait_edit"):
                        focus_widget = focus_widget or self.third_party_wait_edit
        else:
            errors.append("Connect type widget missing.")
        if hasattr(self,
                   "android_version_combo") and connect_type == "Android" and not self.android_version_combo.currentText().strip():
            errors.append("Android version is required.")
            focus_widget = focus_widget or self.android_version_combo
        fpga_valid = (
                hasattr(self, "fpga_customer_combo")
                and hasattr(self, "fpga_product_combo")
                and hasattr(self, "fpga_project_combo")
        )
        customer_text = self.fpga_customer_combo.currentText().strip() if fpga_valid else ""
        product_text = self.fpga_product_combo.currentText().strip() if fpga_valid else ""
        project_text = self.fpga_project_combo.currentText().strip() if fpga_valid else ""
        if not fpga_valid or not customer_text or not product_text or not project_text:
            errors.append("Wi-Fi chipset customer, product line and project are required.")
            if fpga_valid:
                focus_widget = focus_widget or (
                    self.fpga_customer_combo
                    if not customer_text
                    else self.fpga_product_combo
                    if not product_text
                    else self.fpga_project_combo
                )
        if errors:
            from src.ui.controller import show_info_bar
            show_info_bar(
                self,
                "warning",
                "Validation",
                "\n".join(errors),
                duration=3000,
            )
            if focus_widget is not None:
                focus_widget.setFocus()
                if hasattr(focus_widget, "selectAll"):
                    focus_widget.selectAll()
            return False
        return True

    def _validate_test_str_requirements(self) -> bool:
        """Delegate test_str stability validation to config controller."""
        if getattr(self, "config_ctl", None) is not None:
            return self.config_ctl.validate_test_str_requirements()
        return True

    def _is_performance_case(self, abs_case_path) -> bool:
        """Delegate performance-case classification to config controller."""
        return self.config_ctl.is_performance_case(abs_case_path)

    def _is_stability_case(self, case_path: str | Path) -> bool:
        """Delegate stability-case classification to config controller."""
        return self.config_ctl.is_stability_case(case_path)

    def _init_case_tree(self, root_dir: Path) -> None:
        """
        Execute the init case tree routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.fs_model = QFileSystemModel(self.case_tree)
        root_index = self.fs_model.setRootPath(str(root_dir))  # ← use return value
        self.fs_model.setNameFilters(["test_*.py"])
        # show directories regardless of filter
        self.fs_model.setNameFilterDisables(True)
        self.fs_model.setFilter(
            QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Files
        )
        self.proxy_model = TestFileFilterModel()
        self.proxy_model.setSourceModel(self.fs_model)
        self.case_tree.setModel(self.proxy_model)
        self.case_tree.setRootIndex(self.proxy_model.mapFromSource(root_index))

        # hide non-name columns
        self.case_tree.header().hide()
        for col in range(1, self.fs_model.columnCount()):
            self.case_tree.hideColumn(col)

    def _get_application_base(self) -> Path:
        """Get application root path."""
        return Path(get_src_base()).resolve()

    def _normalize_connect_type_label(self, label: str) -> str:
        """
        Execute the normalize connect type label routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        text = (label or "").strip()
        lowered = text.lower()
        if lowered in {"android", "adb"}:
            return "Android"
        if lowered in {"linux", "telnet"}:
            return "Linux"
        return text

    def _current_connect_type(self) -> str:
        """Return the persisted identifier for the selected connect type."""
        if not hasattr(self, "connect_type_combo"):
            return ""
        data = self.connect_type_combo.currentData()
        if isinstance(data, str) and data.strip():
            return data.strip()
        text = self.connect_type_combo.currentText()
        return self._normalize_connect_type_label(text) if isinstance(text, str) else ""

    def _set_connect_type_combo_selection(self, type_value: str) -> None:
        """Select the combo entry matching the stored connect type identifier."""
        if not hasattr(self, "connect_type_combo"):
            return
        target_value = self._normalize_connect_type_label(type_value)
        with QSignalBlocker(self.connect_type_combo):
            index = self.connect_type_combo.findData(target_value)
            if index >= 0:
                self.connect_type_combo.setCurrentIndex(index)
            elif self.connect_type_combo.count():
                self.connect_type_combo.setCurrentIndex(0)


    def _update_android_system_for_connect_type(self, connect_type: str) -> None:
        """Handle non-visual Android system mapping for the given connect type."""
        if not hasattr(self, "android_version_combo") or not hasattr(self, "kernel_version_combo"):
            return
        is_adb = connect_type == "Android"
        if is_adb:
            # For Android, kernel is mapped from the selected Android version.
            self._apply_android_kernel_mapping()
        else:
            # For non-Android, leave kernel editable but clear empty selections.
            if not self.kernel_version_combo.currentText().strip():
                self.kernel_version_combo.setCurrentIndex(-1)

    def _on_android_version_changed(self, version: str) -> None:
        """
        Handle the android version changed event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not hasattr(self, "connect_type_combo"):
            return
        if self._current_connect_type() == "Android":
            self._apply_android_kernel_mapping()

    def _apply_android_kernel_mapping(self) -> None:
        """
        Execute the apply android kernel mapping routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not hasattr(self, "android_version_combo") or not hasattr(self, "kernel_version_combo"):
            return
        version = self.android_version_combo.currentText().strip()
        kernel = ANDROID_KERNEL_MAP.get(version, "")
        if kernel:
            self._ensure_kernel_option(kernel)
            self.kernel_version_combo.setCurrentText(kernel)
        else:
            self.kernel_version_combo.setCurrentIndex(-1)

    def _ensure_kernel_option(self, kernel: str) -> None:
        """
        Execute the ensure kernel option routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not kernel or not hasattr(self, "kernel_version_combo"):
            return
        combo = self.kernel_version_combo
        existing = {combo.itemText(i) for i in range(combo.count())}
        if kernel not in existing:
            combo.addItem(kernel)
        if kernel not in self._kernel_versions:
            self._kernel_versions.append(kernel)

    def on_third_party_toggled(self, checked: bool, allow_wait_edit: bool | None = None) -> None:
        """
        Handle the third party toggled event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        # allow_wait_edit 表示规则层是否允许该字段可编辑;
        # 最终是否 enable 由 (checked and allow_wait_edit) 共同决定.
        enabled = bool(checked)
        if allow_wait_edit is not None:
            enabled = enabled and bool(allow_wait_edit)
        apply_third_party_ui_state(self, enabled)

    def _apply_rf_model_ui_state(self, model_str: str) -> None:
        """Handle pure UI visibility for RF solution parameter groups."""
        apply_rf_model_ui_state(self, model_str)

    def _apply_rvr_tool_ui_state(self, tool: str) -> None:
        """Handle pure UI visibility for RvR tool-specific parameter groups."""
        apply_rvr_tool_ui_state(self, tool)

    def _apply_serial_enabled_ui_state(self, text: str) -> None:
        """Handle pure UI visibility for serial config group."""
        apply_serial_enabled_ui_state(self, text)

    def _register_switch_wifi_csv_combo(self, combo: ComboBox) -> None:
        """Delegate CSV combo registration to the RvR Wi-Fi proxy."""
        _proxy_register_switch_wifi_csv_combo(self, combo)

    def _unregister_switch_wifi_csv_combo(self, combo: ComboBox) -> None:
        """Delegate CSV combo unregistration to the RvR Wi-Fi proxy."""
        _proxy_unregister_switch_wifi_csv_combo(self, combo)

    def _list_available_csv_files(self) -> list[tuple[str, str]]:
        """List CSV files using the RvR Wi-Fi proxy helper."""
        return _proxy_list_available_csv_files()

    def _resolve_csv_config_path(self, value: Any) -> str | None:
        """Resolve persisted CSV paths via the controller helper."""
        return self.config_ctl.resolve_csv_config_path(value)

    def _update_csv_options(self) -> None:
        """Refresh CSV drop-downs via the controller helper."""
        self.config_ctl.update_csv_options()

    def _capture_preselected_csv(self) -> None:
        """Cache CSV selections using the controller helper."""
        self.config_ctl.capture_preselected_csv()

    def _normalize_csv_path(self, path: Any) -> str | None:
        """Normalise CSV paths via the controller helper."""
        return self.config_ctl.normalize_csv_path(path)

    def _relativize_config_path(self, path: Any) -> str:
        """Relativise CSV paths through the controller helper."""
        return self.config_ctl.relativize_config_path(path)

    def _find_csv_index(self, normalized_path: str | None, combo: ComboBox | None = None) -> int:
        """Locate CSV indices using the controller helper."""
        return self.config_ctl.find_csv_index(normalized_path, combo)

    def _set_selected_csv(self, path: str | None, *, sync_combo: bool = True) -> bool:
        """Update CSV selection via the controller helper."""
        return self.config_ctl.set_selected_csv(path, sync_combo=sync_combo)

    def _populate_csv_combo(
            self,
            combo: ComboBox,
            selected_path: str | None,
            *,
            include_placeholder: bool = False,
    ) -> None:
        """Populate CSV combos via the controller helper."""
        self.config_ctl.populate_csv_combo(combo, selected_path, include_placeholder=include_placeholder)

    def _refresh_registered_csv_combos(self) -> None:
        """Refresh CSV combo registrations via the controller helper."""
        self.config_ctl.refresh_registered_csv_combos()

    def _load_switch_wifi_entries(self, csv_path: str | None) -> list[dict[str, str]]:
        """Load Wi-Fi CSV rows through the controller helper."""
        return self.config_ctl.load_switch_wifi_entries(csv_path)

    def _update_switch_wifi_preview(
            self,
            preview: SwitchWifiCsvPreview | None,
            csv_path: str | None,
    ) -> None:
        """Update Wi-Fi preview widgets via the controller helper."""
        self.config_ctl.update_switch_wifi_preview(preview, csv_path)

    def _update_rvr_nav_button(self) -> None:
        """Update the RVR navigation button using the controller helper."""
        self.config_ctl.update_rvr_nav_button()

    def _open_rvr_wifi_config(self) -> None:
        """Open the RVR Wi-Fi configuration page via the controller helper."""
        self.config_ctl.open_rvr_wifi_config()

    def _case_path_to_display(self, case_path: str) -> str:
        """
        Execute the case path to display routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not case_path:
            return ""
        normalized = Path(case_path).as_posix()
        return normalized[5:] if normalized.startswith("test/") else normalized

    def _display_to_case_path(self, display_path: str) -> str:
        """
        Execute the display to case path routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not display_path:
            return ""
        normalized = display_path.replace('\\', '/')
        if normalized.startswith('./'):
            normalized = normalized[2:]
        path_obj = Path(normalized)
        if path_obj.is_absolute() or normalized.startswith('../'):
            return path_obj.as_posix()
        return normalized if normalized.startswith("test/") else f"test/{normalized}"

    def _update_test_case_display(self, storage_path: str) -> None:
        """
        Update the  test case display to reflect current data.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        normalized = Path(storage_path).as_posix() if storage_path else ""
        self._current_case_path = normalized
        if hasattr(self, 'test_case_edit'):
            self.test_case_edit.setText(self._case_path_to_display(normalized))

    def _compose_stability_groups(
            self, active_entry: ScriptConfigEntry | None
    ) -> list[QWidget]:
        """Combine public stability controls with the active script group."""

        groups: list[QWidget] = []
        if self._duration_control_group is not None:
            groups.append(self._duration_control_group)
        if self._check_point_group is not None:
            groups.append(self._check_point_group)
        if active_entry is not None:
            groups.append(active_entry.group)
        return groups

        # valid test case
        if self._refreshing:
            self._pending_path = path
            return
        self.get_editable_fields(path)

    def _apply_editable_info(self, info: EditableInfo | None) -> None:
        """
        Execute the apply editable info routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if getattr(self, "config_ctl", None) is not None:
            self.config_ctl.apply_editable_info(info)

    def _apply_editable_model_state(self, snapshot: EditableInfo) -> None:
        """Backward-compat shim: delegate to controller."""
        if getattr(self, "config_ctl", None) is not None:
            self.config_ctl._apply_editable_model_state(snapshot)

    def _apply_editable_ui_state(self, snapshot: EditableInfo) -> None:
        """Backward-compat shim: delegate to controller."""
        if getattr(self, "config_ctl", None) is not None:
            self.config_ctl._apply_editable_ui_state(snapshot)

    def _restore_editable_state(self) -> None:
        """
        Execute the restore editable state routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if getattr(self, "config_ctl", None) is not None:
            self.config_ctl.restore_editable_state()

    def get_editable_fields(self, case_path) -> EditableInfo:
        """Control field editability after selecting a test case and return related info."""
        if getattr(self, "config_ctl", None) is not None:
            return self.config_ctl.get_editable_fields(str(case_path))
        return EditableInfo()

    def _set_refresh_ui_locked(self, locked: bool) -> None:
        """Lock/unlock tree and global updates while editable info is recomputed."""
        if hasattr(self, "case_tree"):
            self.case_tree.setEnabled(not locked)
        self.setUpdatesEnabled(not locked)

    def set_fields_editable(self, editable_fields: set[str]) -> None:
        """Batch update field editability; DUT area always remains interactive."""
        self.setUpdatesEnabled(False)
        try:
            always_enabled_roots = {"debug", "csv_path"}
            for key, widget in self.field_widgets.items():
                # IxChariot path 的可编辑性由 Execution Settings 中的
                # rvr.tool 下拉（iperf / ixchariot）在 view 层控制，这里不再
                # 覆盖它的 enabled 状态，避免和 apply_rvr_tool_ui_state 冲突。
                if key == "rvr.ixchariot.path":
                    continue
                root_key = key.split(".", 1)[0]
                if self._is_dut_key(root_key) or root_key in always_enabled_roots:
                    desired = True
                else:
                    desired = key in editable_fields
                if widget.isEnabled() == desired:
                    continue
                with QSignalBlocker(widget):
                    widget.setEnabled(desired)
            if hasattr(self, "third_party_checkbox") and hasattr(self, "third_party_wait_edit"):
                allow_wait = (
                    "connect_type.third_party.enabled" in editable_fields
                    and "connect_type.third_party.wait_seconds" in editable_fields
                )
                handle_third_party_toggled_with_permission(
                    self,
                    self.third_party_checkbox.isChecked(),
                    allow_wait,
                )
            self._refresh_script_section_states()
        finally:
            self.setUpdatesEnabled(True)
            self.update()

    def lock_for_running(self, locked: bool) -> None:

        """Enable or disable widgets while a test run is active."""
        if getattr(self, "config_ctl", None) is not None:
            self.config_ctl.lock_for_running(locked)
