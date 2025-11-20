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
from .view.config import RfStepSegmentsWidget, SwitchWifiManualEditor, SwitchWifiCsvPreview
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
from src.ui.view.config.config_str import (
    bind_script_section,
    script_field_key,
    create_test_str_config_entry_from_schema,
    create_test_switch_wifi_config_entry_from_schema,
    initialize_script_config_groups,
)
from .controller.config_ctl import ConfigController
from .view.builder import load_ui_schema, build_groups_from_schema
from .rvrwifi_proxy import (
    _normalize_switch_wifi_manual_entries as _proxy_normalize_switch_wifi_manual_entries,
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
from src import display_to_case_path, case_path_to_display, update_test_case_display
from src.ui.view.config.actions import (
    current_connect_type,
    handle_third_party_toggled_with_permission,
)


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
        # Expose a small helper so view/config glue can register switch‑Wi‑Fi
        # router CSV combos without depending on legacy private methods.
        from src.ui.view.config import register_switch_wifi_csv_combo as _reg_sw_csv
        self.register_switch_wifi_csv_combo = lambda combo: _reg_sw_csv(self, combo)

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
        self._script_config_factories: dict[
            str, Callable[[Any, str, str, Mapping[str, Any]], ScriptConfigEntry]
        ] = {
            "test/stability/test_str.py": create_test_str_config_entry_from_schema,
            "test/stability/test_switch_wifi.py": create_test_switch_wifi_config_entry_from_schema,
        }
        self._script_groups: dict[str, ScriptConfigEntry] = {}
        self._active_script_case: str | None = None
        self._config_panels = tuple(self._page_panels[key] for key in ("dut", "execution", "stability"))
        # render form fields from yaml（委托给 view/config/actions.refresh_config_page_controls）
        self._dut_groups: dict[str, QWidget] = {}
        self._other_groups: dict[str, QWidget] = {}
        refresh_config_page_controls(self)
        initialize_script_config_groups(self)
        # initialise case tree using src/test as root (non-fatal on failure)
        try:
            base = Path(self.config_ctl.get_application_base())
            test_root = base / "test"
            if test_root.exists():
                self.config_ctl.init_case_tree(test_root)
        except Exception:
            pass
        self._refresh_script_section_states()
        self.routerInfoChanged.connect(self.config_ctl.update_csv_options)
        self.config_ctl.update_csv_options()
        # connect signals AFTER UI ready
        self.case_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        QTimer.singleShot(0, lambda: self.config_ctl.get_editable_fields(""))

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
        if current == 0 and target_index > current:
            if getattr(self, "config_ctl", None) is not None:
                if not self.config_ctl.validate_first_page():
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
                script_field_key(case_key, SWITCH_WIFI_USE_ROUTER_FIELD)
            )
            router_combo = entry.widgets.get(
                script_field_key(case_key, SWITCH_WIFI_ROUTER_CSV_FIELD)
            )
            manual_widget = entry.widgets.get(
                script_field_key(case_key, SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
            )
            use_router_value = bool(data.get(SWITCH_WIFI_USE_ROUTER_FIELD))
            if isinstance(use_router_widget, QCheckBox):
                use_router_widget.setChecked(use_router_value)
            router_path = self.config_ctl.resolve_csv_config_path(
                data.get(SWITCH_WIFI_ROUTER_CSV_FIELD)
            )
            if isinstance(router_combo, ComboBox):
                include_placeholder = router_combo.property("switch_wifi_include_placeholder")
                use_placeholder = True if include_placeholder is None else bool(include_placeholder)
                self.config_ctl.populate_csv_combo(
                    router_combo,
                    router_path,
                    include_placeholder=use_placeholder,
                )
                try:
                    self.config_ctl.set_selected_csv(router_path, sync_combo=True)
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

    def _refresh_script_section_states(self) -> None:
        """
        Refresh script section state using the rule engine.
        """
        apply_config_ui_rules(self)

    def _set_refresh_ui_locked(self, locked: bool) -> None:
        """Lock/unlock tree and global updates while editable info is recomputed."""
        if hasattr(self, "case_tree"):
            self.case_tree.setEnabled(not locked)
        self.setUpdatesEnabled(not locked)

    def set_fields_editable(self, fields: set[str]) -> None:
        """Enable or disable config widgets based on the given editable field keys."""
        widgets = getattr(self, "field_widgets", {}) or {}
        for key, widget in widgets.items():
            try:
                enabled = key in fields
                if hasattr(widget, "setEnabled"):
                    widget.setEnabled(enabled)
            except Exception:
                logging.debug("set_fields_editable failed for key=%s", key, exc_info=True)

    # Removed stub method lock_for_running - call config_ctl directly
