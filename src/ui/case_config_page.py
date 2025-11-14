from __future__ import annotations

import copy
import os
import re
from pathlib import Path
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence
from typing import Annotated
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
except Exception:  # pragma: no cover - 运行环境缺失时退化为自定义指示器
    StepView = None
from .animated_tree_view import AnimatedTreeView
from .windows_case_shared import (EditableInfo, ScriptConfigEntry, PAGE_CONTENT_MARGIN, GROUP_COLUMN_SPACING, GROUP_ROW_SPACING, STEP_LABEL_SPACING, USE_QFLUENT_STEP_VIEW, _apply_step_font)
from .windows_case_tree import TestFileFilterModel, _StepSwitcher
from .rf_step_segments import RfStepSegmentsWidget
from .switch_wifi_widgets import SwitchWifiManualEditor, SwitchWifiCsvPreview
from .windows_case_panels import ConfigGroupPanel
from . import build_groupbox
from .sections import build_sections
from .sections.base import ConfigSection, SectionContext
from .config_proxy import ConfigProxy
from .group_proxy import (
    _build_network_group as _proxy_build_network_group,
    _build_traffic_group as _proxy_build_traffic_group,
    _build_duration_group as _proxy_build_duration_group,
    _build_duration_control_group as _proxy_build_duration_control_group,
    _build_check_point_group as _proxy_build_check_point_group,
)
from .run_proxy import on_run as _proxy_on_run
from .rvrwifi_proxy import (
    _normalize_switch_wifi_manual_entries as _proxy_normalize_switch_wifi_manual_entries,
    _register_switch_wifi_csv_combo as _proxy_register_switch_wifi_csv_combo,
    _unregister_switch_wifi_csv_combo as _proxy_unregister_switch_wifi_csv_combo,
    _list_available_csv_files as _proxy_list_available_csv_files,
    _resolve_csv_config_path as _proxy_resolve_csv_config_path,
    _load_csv_selection_from_config as _proxy_load_csv_selection_from_config,
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
from .theme import (
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
        self.config_proxy = ConfigProxy(self)
        apply_theme(self)
        self.selected_csv_path: str | None = None
        # Load the persisted tool configuration and restore CSV selection
        self.config: dict = self._load_config()
        self._config_tool_snapshot: dict[str, Any] = copy.deepcopy(
            self.config.get(TOOL_SECTION_KEY, {})
        )
        self._load_csv_selection_from_config()
        # Initialize transient state flags used by the UI during refreshes and selections
        self._refreshing = False
        self._pending_path: str | None = None
        self.field_widgets: dict[str, QWidget] = {}
        self._section_instances: dict[str, ConfigSection] = {}
        self._section_context = SectionContext()
        self._duration_control_group: QGroupBox | None = None
        self._check_point_group: QGroupBox | None = None
        self.router_obj = None
        self._enable_rvr_wifi: bool = False
        self._router_config_active: bool = False
        self._locked_fields: set[str] | None = None
        self._current_case_path: str = ""
        self._last_editable_info: EditableInfo | None = None
        self._switch_wifi_csv_combos: list[ComboBox] = []
        # Build the main splitter and its left/right panes
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)
        # Populate the left pane with the case tree
        self.case_tree = AnimatedTreeView(self)
        apply_theme(self.case_tree)
        apply_font_and_selection(self.case_tree, size_px=CASE_TREE_FONT_SIZE_PX)
        logging.debug("TreeView font: %s", self.case_tree.font().family())
        logging.debug("TreeView stylesheet: %s", self.case_tree.styleSheet())
        self._init_case_tree(Path(self._get_application_base()) / "test")
        self.splitter.addWidget(self.case_tree)

        # Populate the right pane with parameter controls and the run button
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = scroll_area
        container = QWidget()
        right = QVBoxLayout(container)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(10)
        self._android_versions = list(DEFAULT_ANDROID_VERSION_CHOICES)
        self._kernel_versions = list(DEFAULT_KERNEL_VERSION_CHOICES)
        self._right_layout = right
        self._page_label_map: dict[str, str] = {
            "dut": "DUT Settings",
            "execution": "Execution Settings",
            "stability": "Stability Settings",
        }
        self.step_view_widget = self._create_step_view([self._page_label_map["dut"]])
        self.step_view_widget.setVisible(False)
        right.addWidget(self.step_view_widget)

        self.stack = QStackedWidget(self)
        right.addWidget(self.stack, 1)

        self._page_panels: dict[str, ConfigGroupPanel] = {
            "dut": ConfigGroupPanel(self),
            "execution": ConfigGroupPanel(self),
            "stability": ConfigGroupPanel(self),
        }
        self._dut_panel = self._page_panels["dut"]
        self._execution_panel = self._page_panels["execution"]
        self._stability_panel = self._page_panels["stability"]
        self._page_widgets: dict[str, QWidget] = {}
        self._wizard_pages: list[QWidget] = []
        self._run_buttons: list[PushButton] = []
        self._run_locked = False
        for key in ("dut", "execution", "stability"):
            panel = self._page_panels[key]
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
            )
            page_layout.setSpacing(PAGE_CONTENT_MARGIN)
            page_layout.addWidget(panel)
            page_layout.addStretch(1)
            run_btn = self._create_run_button(page)
            page_layout.addWidget(run_btn)
            self._page_widgets[key] = page
            self._wizard_pages.append(page)
        self._current_page_keys: list[str] = []
        self._script_config_factories: dict[str, Callable[[str, str, Mapping[str, Any]], ScriptConfigEntry]] = {
            "test/stability/test_str.py": self._create_test_str_config_entry,
            "test/stability/test_switch_wifi.py": self._create_test_swtich_wifi_config_entry,
        }
        self._script_groups: dict[str, ScriptConfigEntry] = {}
        self._active_script_case: str | None = None
        self._config_panels = tuple(self._page_panels[key] for key in ("dut", "execution", "stability"))
        self._sync_run_buttons_enabled()
        scroll_area.setWidget(container)
        self.splitter.addWidget(scroll_area)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.addWidget(self.splitter)
        # render form fields from yaml
        self._dut_groups: dict[str, QWidget] = {}
        self._other_groups: dict[str, QWidget] = {}
        self.render_all_fields()
        self._initialize_script_config_groups()
        self._build_wizard_pages()
        self._set_available_pages(["dut"])
        self._refresh_script_section_states()
        self.stack.currentChanged.connect(self._on_page_changed)
        self._request_rebalance_for_panels()
        self._on_page_changed(self.stack.currentIndex())
        self.routerInfoChanged.connect(self._update_csv_options)
        self._update_csv_options()
        # connect signals AFTER UI ready
        self.case_tree.clicked.connect(self.on_case_tree_clicked)
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

    def _create_run_button(self, parent: QWidget) -> PushButton:
        """
        Execute the create run button routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        button = PushButton("Run", parent)
        button.setIcon(FluentIcon.PLAY)
        if hasattr(button, "setUseRippleEffect"):
            button.setUseRippleEffect(True)
        if hasattr(button, "setUseStateEffect"):
            button.setUseStateEffect(True)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.clicked.connect(self.on_run)
        self._run_buttons.append(button)
        return button

    def _create_step_view(self, labels: Sequence[str]) -> QWidget:
        """
        Execute the create step view routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        labels = list(labels)
        if not labels:
            labels = [self._page_label_map["dut"]]
        if StepView is not None and USE_QFLUENT_STEP_VIEW:
            try:
                step_view = StepView(self)
                configured = False
                for attr in ("setSteps", "setStepList", "setStepTextList"):
                    if hasattr(step_view, attr):
                        try:
                            getattr(step_view, attr)(labels)
                            configured = True
                            break
                        except Exception as exc:
                            logging.debug("StepView.%s failed: %s", attr, exc)
                if not configured and hasattr(step_view, "addStep"):
                    add_step = getattr(step_view, "addStep")
                    for label in labels:
                        try:
                            add_step(label)
                        except TypeError:
                            add_step(label, label)
                for attr in (
                        "setStepNumberVisible",
                        "setNumberVisible",
                        "setIndexVisible",
                        "setShowNumber",
                        "setDisplayIndex",
                ):
                    if hasattr(step_view, attr):
                        try:
                            getattr(step_view, attr)(False)
                        except Exception as exc:
                            logging.debug("StepView.%s failed: %s", attr, exc)
                for attr in ("setStepClickable", "setStepsClickable", "setAllClickable"):
                    if hasattr(step_view, attr):
                        try:
                            getattr(step_view, attr)(True)
                        except Exception as exc:
                            logging.debug("StepView.%s failed: %s", attr, exc)
                self._attach_step_navigation(step_view)
                _apply_step_font(step_view)
                return step_view
            except Exception as exc:  # pragma: no cover - 动态环境差异
                logging.debug("Failed to initialize StepView: %s", exc)
        fallback = _StepSwitcher(labels, self)
        fallback.stepActivated.connect(self._on_step_activated)
        return fallback

    def _update_step_indicator(self, index: int) -> None:
        """
        Update the  step indicator to reflect current data.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        view = getattr(self, "step_view_widget", None)
        if view is None:
            return
        for attr in ("setCurrentIndex", "setCurrentStep", "setCurrentRow", "setCurrent"):
            if hasattr(view, attr):
                try:
                    getattr(view, attr)(index)
                    return
                except Exception as exc:
                    logging.debug("StepView %s failed: %s", attr, exc)
        if hasattr(view, "set_current_index"):
            try:
                view.set_current_index(index)
            except Exception as exc:
                logging.debug("Fallback step indicator failed: %s", exc)

    def _attach_step_navigation(self, view: QWidget) -> None:
        """
        Execute the attach step navigation routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if isinstance(view, _StepSwitcher):
            view.stepActivated.connect(self._on_step_activated)
            return
        handler_connected = False

        def _handler(*args, **kwargs):
            """
            Execute the handler routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            index = self._coerce_step_index(*(args or []), *(kwargs.values()))
            if index is not None:
                self._on_step_activated(index)

        for signal_name in (
                "stepClicked",
                "currentIndexChanged",
                "currentChanged",
                "currentRowChanged",
                "clicked",
                "activated",
        ):
            signal = getattr(view, signal_name, None)
            if signal is None or not hasattr(signal, "connect"):
                continue
            try:
                signal.connect(_handler)
                handler_connected = True
                break
            except Exception as exc:
                logging.debug("Failed to connect StepView.%s: %s", signal_name, exc)
        if handler_connected:
            return
        for child in view.findChildren(QWidget):
            if child is view:
                continue
            try:
                self._attach_step_navigation(child)
                handler_connected = True
                break
            except Exception as exc:
                logging.debug("StepView child hookup failed: %s", exc)
        if not handler_connected:
            logging.debug("Step navigation hookup failed; relying on fallback behaviour")

    def _on_step_activated(self, *args) -> None:
        """
        Handle the step activated event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        index = self._coerce_step_index(*args)
        if index is None:
            return
        self._navigate_to_index(index)

    def _coerce_step_index(self, *args) -> Optional[int]:
        """
        Execute the coerce step index routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        for arg in args:
            if isinstance(arg, int):
                return arg
            if isinstance(arg, (list, tuple)):
                nested = self._coerce_step_index(*arg)
                if nested is not None:
                    return nested
            if isinstance(arg, str) and arg.strip().isdigit():
                return int(arg.strip())
            if hasattr(arg, "row") and callable(getattr(arg, "row")):
                row = arg.row()
                if isinstance(row, int) and row >= 0:
                    return row
            if isinstance(arg, Mapping) and "index" in arg:
                nested = self._coerce_step_index(arg["index"])
                if nested is not None:
                    return nested
            if hasattr(arg, "index"):
                idx = getattr(arg, "index")
                if isinstance(idx, int):
                    return idx
        return None

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
        self._sync_widgets_to_config()
        self.stack.setCurrentIndex(target_index)

    def _sync_run_buttons_enabled(self) -> None:
        """
        Execute the sync run buttons enabled routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        enabled = not self._run_locked
        for btn in self._run_buttons:
            btn.setEnabled(enabled)

    def _info_bar_parent(self) -> QWidget:
        """
        Execute the info bar parent routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        parent = self.window()
        if isinstance(parent, QWidget):
            return parent
        return self

    def _show_info_bar(
            self,
            level: str,
            title: str,
            content: str,
            **kwargs: Any,
    ):
        """
        Execute the show info bar routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        bar_fn = getattr(InfoBar, level, None)
        if not callable(bar_fn):
            logging.debug("InfoBar level %s unavailable", level)
            return None
        info_parent = self._info_bar_parent()
        params = {
            "title": title,
            "content": content,
            "parent": info_parent,
            "position": InfoBarPosition.TOP,
        }
        params.update(kwargs)
        try:
            bar = bar_fn(**params)
        except Exception as exc:
            logging.debug("InfoBar.%s failed: %s", level, exc)
            return None
        scroll = getattr(self, "scroll_area", None)
        if scroll is not None:
            try:
                scrollbar = scroll.verticalScrollBar()
                if scrollbar is not None:
                    scrollbar.setValue(scrollbar.minimum())
            except Exception as exc:
                logging.debug("Failed to reset scroll position: %s", exc)
        if hasattr(bar, "raise_"):
            bar.raise_()
        if hasattr(info_parent, "raise_"):
            info_parent.raise_()
        if hasattr(info_parent, "activateWindow"):
            info_parent.activateWindow()
        return bar

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
        Execute the compose other groups routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        return list(self._other_groups.values())

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

    def _refresh_step_view(self, page_keys: Sequence[str]) -> None:
        """
        Refresh the  step view to ensure the UI is up to date.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        labels = [self._page_label_map.get(key, key.title()) for key in page_keys]
        if not labels:
            labels = [self._page_label_map["dut"]]
        new_view = self._create_step_view(labels)
        old_view = getattr(self, "step_view_widget", None)
        layout = getattr(self, "_right_layout", None)
        if layout is not None:
            if old_view is not None:
                index = layout.indexOf(old_view)
                if index < 0:
                    index = 0
                layout.insertWidget(index, new_view)
                layout.removeWidget(old_view)
                old_view.setParent(None)
            else:
                layout.insertWidget(0, new_view)
        self.step_view_widget = new_view
        self.step_view_widget.setVisible(len(page_keys) > 1)

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
        if normalized == getattr(self, "_current_page_keys", []):
            return
        current_widget = self.stack.currentWidget() if self.stack.count() else None
        current_key: str | None = None
        if current_widget is not None:
            for key, widget in self._page_widgets.items():
                if widget is current_widget:
                    current_key = key
                    break
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
        for key in normalized:
            self.stack.addWidget(self._page_widgets[key])
        self._current_page_keys = normalized
        self._refresh_step_view(normalized)
        target_index = 0
        if current_key in normalized:
            target_index = normalized.index(current_key)
        self.stack.setCurrentIndex(target_index)
        self._update_step_indicator(target_index)
        if hasattr(self, "step_view_widget") and self.step_view_widget is not None:
            self.step_view_widget.setVisible(len(self._current_page_keys) > 1)
        self._update_navigation_state()

    def _determine_pages_for_case(self, case_path: str, info: EditableInfo) -> list[str]:

        """
        Execute the determine pages for case routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not case_path:
            return ["dut"]
        keys = ["dut"]
        if self._is_performance_case(case_path) or info.enable_csv:
            if "execution" not in keys:
                keys.append("execution")
        else:
            case_key = self._script_case_key(case_path)
            if case_key in self._script_groups:
                keys.append("stability")
        return keys

    def _script_case_key(self, case_path: str | Path) -> str:
        """
        Execute the script case key routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not case_path:
            return ""
        path_obj = case_path if isinstance(case_path, Path) else Path(case_path)
        if path_obj.is_absolute():
            try:
                path_obj = path_obj.resolve().relative_to(self._get_application_base())
            except ValueError:
                path_obj = path_obj.resolve()
        stem = path_obj.stem.lower()
        if stem in SWITCH_WIFI_CASE_KEYS:
            return SWITCH_WIFI_CASE_KEY
        return stem

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
            entry_config = self._ensure_script_case_defaults(case_key, case_path)
            entry = factory(case_key, case_path, entry_config)
            entry.group.setVisible(False)
            self._script_groups[case_key] = entry
            self.field_widgets.update(entry.widgets)
        self._stability_panel.set_groups(self._compose_stability_groups(None))

    @staticmethod
    def _normalize_switch_wifi_manual_entries(entries: Any) -> list[dict[str, str]]:
        """Proxy to normalise manual Wi-Fi entries for switch Wi-Fi cases."""
        return _proxy_normalize_switch_wifi_manual_entries(entries)

    def _ensure_script_case_defaults(self, case_key: str, case_path: str) -> dict[str, Any]:
        """Delegate stability case defaults to the config proxy."""
        return self.config_proxy.ensure_script_case_defaults(case_key, case_path)

    def _update_script_config_ui(self, case_path: str | Path) -> None:
        """
        Update the  script config ui to reflect current data.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        case_key = self._script_case_key(case_path)
        changed = False
        active_entry: ScriptConfigEntry | None = None
        if case_key not in self._script_groups:
            if self._active_script_case is not None:
                self._active_script_case = None
                for entry in self._script_groups.values():
                    if entry.group.isVisible():
                        entry.group.setVisible(False)
                self._stability_panel.set_groups([])
                self._request_rebalance_for_panels(self._stability_panel)
            self._refresh_script_section_states()
            return
        if self._active_script_case != case_key:
            self._active_script_case = case_key
            changed = True
        for key, entry in self._script_groups.items():
            visible = key == case_key
            if entry.group.isVisible() != visible:
                entry.group.setVisible(visible)
                changed = True
            if visible:
                data = self._ensure_script_case_defaults(key, entry.case_path)
                self._load_script_config_into_widgets(entry, data)
                active_entry = entry
        if active_entry is not None:
            self._stability_panel.set_groups(self._compose_stability_groups(active_entry))
        else:
            self._stability_panel.set_groups([])
        self._request_rebalance_for_panels(self._stability_panel)
        self._refresh_script_section_states()

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
            if isinstance(manual_widget, SwitchWifiManualEditor):
                manual_entries = data.get(SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
                if isinstance(manual_entries, Sequence) and not isinstance(manual_entries, (str, bytes)):
                    manual_widget.set_entries(manual_entries)
                else:
                    manual_widget.set_entries(None)
            extras = entry.extras if isinstance(entry.extras, dict) else {}
            preview: SwitchWifiCsvPreview | None = extras.get("router_preview")
            self._update_switch_wifi_preview(preview, router_path)
            sync_router_csv = extras.get("sync_router_csv")
            if sync_router_csv is not None:
                try:
                    sync_router_csv(router_path, emit=use_router_value)
                except Exception as exc:
                    logging.debug("sync_router_csv failed: %s", exc)
            apply_mode = extras.get("apply_mode")
            if apply_mode is not None:
                try:
                    apply_mode(use_router_value)
                except Exception as exc:
                    logging.debug("apply_mode failed: %s", exc)
            return

        ac_cfg = data.get("ac", {})
        str_cfg = data.get("str", {})

        def _set_spin(key: str, raw_value: Any) -> None:
            """
            Set the spin property on the instance.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            widget = entry.widgets.get(key)
            if isinstance(widget, QSpinBox):
                try:
                    value = int(raw_value)
                except (TypeError, ValueError):
                    value = 0
                with QSignalBlocker(widget):
                    widget.setValue(max(0, value))

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

        for checkbox, controls in entry.section_controls.values():
            self._set_section_controls_state(controls, checkbox.isChecked())

    @staticmethod
    def _set_section_controls_state(controls: Sequence[QWidget], enabled: bool) -> None:
        """
        Set the section controls state property on the instance.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        for widget in controls:
            widget.setEnabled(enabled)

    def _refresh_script_section_states(self) -> None:
        """
        Refresh the  script section states to ensure the UI is up to date.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        for entry in self._script_groups.values():
            for checkbox, controls in entry.section_controls.values():
                self._set_section_controls_state(controls, checkbox.isEnabled() and checkbox.isChecked())

    def _bind_script_section(self, checkbox: QCheckBox, controls: Sequence[QWidget]) -> None:
        """
        Execute the bind script section routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """

        def _apply(checked: bool) -> None:
            """
            Execute the apply routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            self._set_section_controls_state(controls, checked)

        checkbox.toggled.connect(_apply)
        _apply(checkbox.isChecked())

    def _create_test_swtich_wifi_config_entry(
            self,
            case_key: str,
            case_path: str,
            data: Mapping[str, Any],
    ) -> ScriptConfigEntry:
        """
        Execute the create test switch wifi config entry routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        group = QGroupBox("test_switch_wifi.py Stability", self)
        apply_theme(group)
        apply_groupbox_style(group)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        intro = QLabel(
            "Configure Wi-Fi BSS targets for test_switch_wifi."
            " Select router CSV to reuse predefined entries or maintain manual list.",
            group,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        use_router_checkbox = QCheckBox("Use router configuration", group)
        use_router_checkbox.setChecked(bool(data.get(SWITCH_WIFI_USE_ROUTER_FIELD)))
        layout.addWidget(use_router_checkbox)

        router_box = QGroupBox("Router CSV", group)
        apply_theme(router_box)
        apply_groupbox_style(router_box)
        router_layout = QVBoxLayout(router_box)
        router_layout.setContentsMargins(8, 8, 8, 8)
        router_layout.setSpacing(6)

        router_combo = ComboBox(router_box)
        router_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        router_combo.setProperty("switch_wifi_include_placeholder", False)
        router_layout.addWidget(router_combo)

        router_selector = ComboBox(router_box)
        router_selector.addItems(router_list.keys())
        router_selector.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        router_layout.addWidget(router_selector)

        router_preview = SwitchWifiCsvPreview(router_box)
        router_layout.addWidget(router_preview)

        manual_box = QGroupBox("Manual entries", group)
        apply_theme(manual_box)
        apply_groupbox_style(manual_box)
        manual_layout = QVBoxLayout(manual_box)
        manual_layout.setContentsMargins(8, 8, 8, 8)
        manual_layout.setSpacing(6)

        manual_editor = SwitchWifiManualEditor(manual_box)
        manual_entries = (
            data.get(SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
            if isinstance(data, Mapping)
            else None
        )
        if isinstance(manual_entries, Sequence) and not isinstance(manual_entries, (str, bytes)):
            manual_editor.set_entries(manual_entries)
        else:
            manual_editor.set_entries(None)
        manual_layout.addWidget(manual_editor)

        layout.addWidget(router_box)
        layout.addWidget(manual_box)
        layout.addStretch(1)

        router_path = self._resolve_csv_config_path(
            data.get(SWITCH_WIFI_ROUTER_CSV_FIELD)
        )
        self._populate_csv_combo(router_combo, router_path, include_placeholder=False)
        placeholder_index = router_combo.findData("")
        if placeholder_index >= 0 and router_combo.count() > 1:
            router_combo.removeItem(placeholder_index)
        self._register_switch_wifi_csv_combo(router_combo)
        self._update_switch_wifi_preview(router_preview, router_path)

        primary_router_combo = getattr(self, "router_name_combo", None)
        if isinstance(primary_router_combo, ComboBox):
            with QSignalBlocker(router_selector):
                router_selector.setCurrentText(primary_router_combo.currentText())
        else:
            router_cfg = self.config.get("router") if isinstance(self.config, Mapping) else {}
            if isinstance(router_cfg, Mapping):
                default_router = str(router_cfg.get("name", ""))
                if default_router:
                    with QSignalBlocker(router_selector):
                        router_selector.setCurrentText(default_router)

        def _sync_router_selector(name: str) -> None:
            """Keep the router selector aligned with the primary router combo."""
            with QSignalBlocker(router_selector):
                router_selector.setCurrentText(name)

        if isinstance(primary_router_combo, ComboBox):
            primary_router_combo.currentTextChanged.connect(_sync_router_selector)

        def _on_router_model_selected(name: str) -> None:
            """Propagate router model changes back to the main router combo."""
            base_combo = getattr(self, "router_name_combo", None)
            if isinstance(base_combo, ComboBox):
                with QSignalBlocker(base_combo):
                    base_combo.setCurrentText(name)
                try:
                    self.on_router_changed(name)
                except Exception as exc:  # pragma: no cover - defensive log only
                    logging.debug("router selector sync failed: %s", exc)

        router_selector.currentTextChanged.connect(_on_router_model_selected)

        widgets: dict[str, QWidget] = {}
        widgets[
            self._script_field_key(case_key, SWITCH_WIFI_USE_ROUTER_FIELD)
        ] = use_router_checkbox
        widgets[
            self._script_field_key(case_key, SWITCH_WIFI_ROUTER_CSV_FIELD)
        ] = router_combo
        widgets[
            self._script_field_key(case_key, SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
        ] = manual_editor

        section_controls: dict[str, tuple[QCheckBox, Sequence[QWidget]]] = {}

        router_mode_state: dict[str, bool] = {"suppress_open": True}

        def _current_csv_selection() -> str | None:
            """
            Execute the current csv selection routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            data_value = router_combo.currentData()
            if isinstance(data_value, str) and data_value:
                return data_value
            text_value = router_combo.currentText()
            return text_value if isinstance(text_value, str) and text_value else None

        def _sync_case_csv(path: str | None = None, *, emit: bool = True) -> bool:
            target = path if path is not None else _current_csv_selection()
            changed = self._set_selected_csv(target, sync_combo=False)
            if changed and emit:
                self.csvFileChanged.emit(self.selected_csv_path or "")
            return changed

        def _apply_mode(checked: bool) -> None:
            """
            Execute the apply mode routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            router_box.setVisible(checked)
            manual_box.setVisible(not checked)
            manual_editor.setEnabled(not checked)
            self._router_config_active = checked
            if checked:
                router_selector.setEnabled(True)
                _sync_case_csv(path=_current_csv_selection(), emit=True)
            else:
                router_selector.setEnabled(False)
                cleared = self._set_selected_csv(None, sync_combo=False)
                if cleared:
                    self.csvFileChanged.emit("")
            self._update_switch_wifi_preview(router_preview, _current_csv_selection())
            self._request_rebalance_for_panels(self._stability_panel)
            self._update_rvr_nav_button()

        def _on_csv_changed() -> None:
            """
            Handle the csv changed event triggered by user interaction.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            selection = _current_csv_selection()
            self._update_switch_wifi_preview(router_preview, selection)
            if use_router_checkbox.isChecked():
                _sync_case_csv(path=selection, emit=True)

        router_combo.currentIndexChanged.connect(lambda _index: _on_csv_changed())
        use_router_checkbox.toggled.connect(_apply_mode)
        router_selector.setEnabled(use_router_checkbox.isChecked())

        router_selector.setEnabled(use_router_checkbox.isChecked())

        entry = ScriptConfigEntry(
            group=group,
            widgets=widgets,
            field_keys=set(widgets.keys()),
            section_controls=section_controls,
            case_key=case_key,
            case_path=case_path,
            extras={
                "router_preview": router_preview,
                "router_combo": router_combo,
                "apply_mode": _apply_mode,
                "router_box": router_box,
                "manual_box": manual_box,
                "manual_editor": manual_editor,
                "router_selector": router_selector,
                "sync_router_csv": _sync_case_csv,
                "use_router_checkbox": use_router_checkbox,
            },
        )

        _apply_mode(use_router_checkbox.isChecked())

        return entry

    def _create_test_str_config_entry(
            self,
            case_key: str,
            case_path: str,
            data: Mapping[str, Any],
    ) -> ScriptConfigEntry:
        """
        Execute the create test str config entry routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        group = QGroupBox("test_str.py Stability", self)
        apply_theme(group)
        apply_groupbox_style(group)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        intro = QLabel("Configure AC/STR cycling parameters for test_str.py.", group)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        widgets: dict[str, QWidget] = {}
        section_controls: dict[str, tuple[QCheckBox, Sequence[QWidget]]] = {}

        def _build_port_combo(parent: QWidget) -> ComboBox:
            """
            Execute the build port combo routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            combo = ComboBox(parent)
            combo.setMinimumWidth(220)
            combo.addItem("Select port", "")

            def _refresh_ports(preserve_current: bool = True) -> None:
                """Reload available serial ports while optionally preserving selection."""
                current_value = ""
                if preserve_current:
                    data = combo.currentData()
                    if isinstance(data, str):
                        current_value = data
                combo.blockSignals(True)
                try:
                    combo.clear()
                    combo.addItem("Select port", "")
                    for device, label in self._list_serial_ports():
                        combo.addItem(label, device)
                    if current_value:
                        index = combo.findData(current_value)
                        if index < 0:
                            combo.addItem(current_value, current_value)
                            index = combo.findData(current_value)
                        combo.setCurrentIndex(index if index >= 0 else 0)
                    else:
                        combo.setCurrentIndex(0)
                finally:
                    combo.blockSignals(False)

            combo.refresh_ports = _refresh_ports  # type: ignore[attr-defined]
            _refresh_ports(preserve_current=False)

            original_show_popup = getattr(combo, "showPopup", None)
            if callable(original_show_popup):

                def _show_popup() -> None:
                    """Refresh port list whenever the dropdown is opened."""
                    try:
                        _refresh_ports()
                    finally:
                        original_show_popup()

                combo.showPopup = _show_popup  # type: ignore[method-assign]
            else:

                class _PortPopupEventFilter(QObject):
                    """Event filter ensuring USB ports refresh before combo opens."""

                    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # type: ignore[override]
                        """
                        Filter events for child widgets and emit signals when appropriate.

                        This method encapsulates the logic necessary to perform its function.
                        Refer to the implementation for details on parameters and return values.
                        """
                        if event.type() == QEvent.MouseButtonPress:
                            _refresh_ports()
                        return False

                popup_filter = _PortPopupEventFilter(combo)
                combo._port_popup_filter = popup_filter  # type: ignore[attr-defined]
                combo.installEventFilter(popup_filter)
            return combo

        def _set_port_default(combo: ComboBox, value: str) -> None:
            """
            Set the port default property on the instance.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            value = (value or "").strip()
            refresh_ports = getattr(combo, "refresh_ports", None)
            if callable(refresh_ports):
                refresh_ports(preserve_current=False)
            if not value:
                combo.setCurrentIndex(0 if combo.count() else -1)
                return
            index = combo.findData(value)
            if index < 0:
                combo.addItem(value, value)
                index = combo.findData(value)
            combo.setCurrentIndex(index if index >= 0 else 0)

        def _set_mode_default(combo: ComboBox, value: str) -> None:
            """
            Set the mode default property on the instance.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            target = (value or "NO").strip().upper() or "NO"
            # ComboBoxBase.findText only supports the text argument, so we perform
            # an explicit case-insensitive match to keep the previous behavior.
            index = next(
                (i for i in range(combo.count()) if combo.itemText(i).strip().upper() == target),
                -1,
            )
            if index < 0:
                combo.addItem(target)
                index = next(
                    (i for i in range(combo.count()) if combo.itemText(i).strip().upper() == target),
                    -1,
                )
            combo.setCurrentIndex(index if index >= 0 else 0)

        def _set_relay_type_default(combo: ComboBox, value: str) -> None:
            """Select the relay type option matching the stored value."""

            target = (value or "usb_relay").strip()
            if not target:
                target = "usb_relay"
            normalized = target.lower()
            relay_display_map = {
                "usb_relay": "USB Relay",
                "gwgj-xc3012": "GWGJ-XC3012",
            }
            display_text = relay_display_map.get(normalized, target)
            # Remove empty placeholder entries that have no visible effect.
            for index in range(combo.count() - 1, -1, -1):
                if not combo.itemText(index).strip() and combo.itemData(index) is None:
                    combo.removeItem(index)
            index = next(
                (
                    i
                    for i in range(combo.count())
                    if isinstance(combo.itemData(i), str)
                    and combo.itemData(i).strip().lower() == normalized
                ),
                -1,
            )
            if index < 0:
                index = next(
                    (i for i in range(combo.count()) if combo.itemText(i).strip().lower() == display_text.lower()),
                    -1,
                )
            if index < 0 and target:
                combo.addItem(display_text, target)
                index = next(
                    (
                        i
                        for i in range(combo.count())
                        if isinstance(combo.itemData(i), str)
                        and combo.itemData(i).strip().lower() == normalized
                    ),
                    combo.count() - 1,
                )
            combo.setCurrentIndex(index if index >= 0 else 0)

        def _configure_relay_controls(
            checkbox: QCheckBox,
            combo: ComboBox,
            usb_widgets: Sequence[QWidget],
            snmp_widgets: Sequence[QWidget],
        ) -> None:
            """Toggle USB/SNMP specific widgets based on the selected relay type."""

            def _apply(*_args: object) -> None:
                data_value = combo.currentData()
                relay_value = data_value if isinstance(data_value, str) else combo.currentText()
                key = (relay_value or "").strip().lower().replace(" ", "_")
                is_usb = key in {"usb_relay"}
                section_enabled = checkbox.isChecked()
                for widget in usb_widgets:
                    widget.setEnabled(section_enabled and is_usb)
                for widget in snmp_widgets:
                    widget.setEnabled(section_enabled and not is_usb)

            combo.currentIndexChanged.connect(_apply)
            checkbox.toggled.connect(_apply)
            _apply()

        ac_checkbox = QCheckBox("Enable AC cycle", group)
        layout.addWidget(ac_checkbox)

        ac_grid = QGridLayout()
        ac_grid.setContentsMargins(24, 0, 0, 0)
        ac_grid.setHorizontalSpacing(12)
        ac_grid.setVerticalSpacing(6)

        ac_on_label = QLabel("AC on duration (s)", group)
        ac_on_spin = QSpinBox(group)
        ac_on_spin.setRange(0, 24 * 60 * 60)
        ac_on_spin.setSuffix(" s")

        ac_off_label = QLabel("AC off duration (s)", group)
        ac_off_spin = QSpinBox(group)
        ac_off_spin.setRange(0, 24 * 60 * 60)
        ac_off_spin.setSuffix(" s")

        ac_port_label = QLabel("USB relay port", group)
        ac_port_combo = _build_port_combo(group)

        ac_mode_label = QLabel("Wiring mode", group)
        ac_mode_combo = ComboBox(group)
        ac_mode_combo.setMinimumWidth(160)
        ac_mode_combo.addItems(["NO", "NC"])

        ac_relay_type_label = QLabel("Relay type", group)
        ac_relay_type_combo = ComboBox(group)
        ac_relay_type_combo.setMinimumWidth(200)
        ac_relay_type_combo.addItem("USB Relay", "usb_relay")
        ac_relay_type_combo.addItem("GWGJ-XC3012", "GWGJ-XC3012")

        ac_params_label = QLabel("Relay params (ip,port)", group)
        ac_params_edit = LineEdit(group)
        ac_params_edit.setPlaceholderText("192.168.0.10,4")

        ac_grid.addWidget(ac_on_label, 0, 0)
        ac_grid.addWidget(ac_on_spin, 0, 1)
        ac_grid.addWidget(ac_off_label, 1, 0)
        ac_grid.addWidget(ac_off_spin, 1, 1)
        ac_grid.addWidget(ac_port_label, 2, 0)
        ac_grid.addWidget(ac_port_combo, 2, 1)
        ac_grid.addWidget(ac_mode_label, 3, 0)
        ac_grid.addWidget(ac_mode_combo, 3, 1)
        ac_grid.addWidget(ac_relay_type_label, 4, 0)
        ac_grid.addWidget(ac_relay_type_combo, 4, 1)
        ac_grid.addWidget(ac_params_label, 5, 0)
        ac_grid.addWidget(ac_params_edit, 5, 1)
        layout.addLayout(ac_grid)

        self._bind_script_section(
            ac_checkbox,
            (
                ac_on_spin,
                ac_off_spin,
                ac_port_combo,
                ac_mode_combo,
                ac_relay_type_combo,
                ac_params_edit,
            ),
        )
        section_controls["ac"] = (
            ac_checkbox,
            (
                ac_on_spin,
                ac_off_spin,
                ac_port_combo,
                ac_mode_combo,
                ac_relay_type_combo,
                ac_params_edit,
            ),
        )

        str_checkbox = QCheckBox("Enable STR cycle", group)
        layout.addWidget(str_checkbox)

        str_grid = QGridLayout()
        str_grid.setContentsMargins(24, 0, 0, 0)
        str_grid.setHorizontalSpacing(12)
        str_grid.setVerticalSpacing(6)

        str_on_label = QLabel("STR on duration (s)", group)
        str_on_spin = QSpinBox(group)
        str_on_spin.setRange(0, 24 * 60 * 60)
        str_on_spin.setSuffix(" s")

        str_off_label = QLabel("STR off duration (s)", group)
        str_off_spin = QSpinBox(group)
        str_off_spin.setRange(0, 24 * 60 * 60)
        str_off_spin.setSuffix(" s")

        str_relay_type_label = QLabel("Relay type", group)
        str_relay_type_combo = ComboBox(group)
        str_relay_type_combo.setMinimumWidth(200)
        str_relay_type_combo.addItem("USB Relay", "usb_relay")
        str_relay_type_combo.addItem("GWGJ-XC3012", "GWGJ-XC3012")

        str_port_label = QLabel("USB relay port", group)
        str_port_combo = _build_port_combo(group)

        str_mode_label = QLabel("Wiring mode", group)
        str_mode_combo = ComboBox(group)
        str_mode_combo.setMinimumWidth(160)
        str_mode_combo.addItems(["NO", "NC"])

        str_params_label = QLabel("Relay params (ip,port)", group)
        str_params_edit = LineEdit(group)
        str_params_edit.setPlaceholderText("192.168.0.10,4")

        str_grid.addWidget(str_on_label, 0, 0)
        str_grid.addWidget(str_on_spin, 0, 1)
        str_grid.addWidget(str_off_label, 1, 0)
        str_grid.addWidget(str_off_spin, 1, 1)
        str_grid.addWidget(str_relay_type_label, 2, 0)
        str_grid.addWidget(str_relay_type_combo, 2, 1)
        str_grid.addWidget(str_port_label, 3, 0)
        str_grid.addWidget(str_port_combo, 3, 1)
        str_grid.addWidget(str_mode_label, 4, 0)
        str_grid.addWidget(str_mode_combo, 4, 1)
        str_grid.addWidget(str_params_label, 5, 0)
        str_grid.addWidget(str_params_edit, 5, 1)
        layout.addLayout(str_grid)

        self._bind_script_section(
            str_checkbox,
            (
                str_on_spin,
                str_off_spin,
                str_port_combo,
                str_mode_combo,
                str_relay_type_combo,
                str_params_edit,
            ),
        )
        section_controls["str"] = (
            str_checkbox,
            (
                str_on_spin,
                str_off_spin,
                str_port_combo,
                str_mode_combo,
                str_relay_type_combo,
                str_params_edit,
            ),
        )

        layout.addStretch(1)

        ac_cfg = data.get("ac", {})
        str_cfg = data.get("str", {})

        ac_checkbox.setChecked(bool(ac_cfg.get("enabled")))
        ac_on_spin.setValue(int(ac_cfg.get("on_duration") or 0))
        ac_off_spin.setValue(int(ac_cfg.get("off_duration") or 0))
        ac_port = str(ac_cfg.get("port", "") or "").strip()
        ac_mode = str(ac_cfg.get("mode", "") or "").strip().upper() or "NO"
        ac_type = str(ac_cfg.get("relay_type", "usb_relay") or "usb_relay").strip()
        ac_params = ac_cfg.get("relay_params")
        if isinstance(ac_params, (list, tuple)):
            ac_params_text = ", ".join(str(item) for item in ac_params if str(item).strip())
        elif isinstance(ac_params, str):
            ac_params_text = ac_params
        else:
            ac_params_text = ""
        _set_port_default(ac_port_combo, ac_port)
        _set_mode_default(ac_mode_combo, ac_mode)
        _set_relay_type_default(ac_relay_type_combo, ac_type)
        ac_params_edit.setText(ac_params_text)

        str_checkbox.setChecked(bool(str_cfg.get("enabled")))
        str_on_spin.setValue(int(str_cfg.get("on_duration") or 0))
        str_off_spin.setValue(int(str_cfg.get("off_duration") or 0))
        str_port = str(str_cfg.get("port", "") or "").strip()
        str_mode = str(str_cfg.get("mode", "") or "").strip().upper() or "NO"
        str_type = str(str_cfg.get("relay_type", "usb_relay") or "usb_relay").strip()
        str_params = str_cfg.get("relay_params")
        if isinstance(str_params, (list, tuple)):
            str_params_text = ", ".join(str(item) for item in str_params if str(item).strip())
        elif isinstance(str_params, str):
            str_params_text = str_params
        else:
            str_params_text = ""
        _set_port_default(str_port_combo, str_port)
        _set_mode_default(str_mode_combo, str_mode)
        _set_relay_type_default(str_relay_type_combo, str_type)
        str_params_edit.setText(str_params_text)

        _configure_relay_controls(
            ac_checkbox,
            ac_relay_type_combo,
            (ac_port_label, ac_port_combo, ac_mode_label, ac_mode_combo),
            (ac_params_label, ac_params_edit),
        )
        _configure_relay_controls(
            str_checkbox,
            str_relay_type_combo,
            (str_port_label, str_port_combo, str_mode_label, str_mode_combo),
            (str_params_label, str_params_edit),
        )

        widgets[self._script_field_key(case_key, "ac", "enabled")] = ac_checkbox
        widgets[self._script_field_key(case_key, "ac", "on_duration")] = ac_on_spin
        widgets[self._script_field_key(case_key, "ac", "off_duration")] = ac_off_spin
        widgets[self._script_field_key(case_key, "ac", "port")] = ac_port_combo
        widgets[self._script_field_key(case_key, "ac", "mode")] = ac_mode_combo
        widgets[self._script_field_key(case_key, "ac", "relay_type")] = ac_relay_type_combo
        widgets[self._script_field_key(case_key, "ac", "relay_params")] = ac_params_edit

        widgets[self._script_field_key(case_key, "str", "enabled")] = str_checkbox
        widgets[self._script_field_key(case_key, "str", "on_duration")] = str_on_spin
        widgets[self._script_field_key(case_key, "str", "off_duration")] = str_off_spin
        widgets[self._script_field_key(case_key, "str", "port")] = str_port_combo
        widgets[self._script_field_key(case_key, "str", "mode")] = str_mode_combo
        widgets[self._script_field_key(case_key, "str", "relay_type")] = str_relay_type_combo
        widgets[self._script_field_key(case_key, "str", "relay_params")] = str_params_edit

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
        Execute the register group routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if is_dut:
            self._dut_groups[key] = group
        else:
            self._other_groups[key] = group

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
            "android_system",
        }

    def _normalize_fpga_token(self, value: Any) -> str:
        """Normalise FPGA identifier tokens via the config proxy."""
        return self.config_proxy.normalize_fpga_token(value)

    @staticmethod
    def _split_legacy_fpga_value(raw: str) -> tuple[str, str]:
        """
        Execute the split legacy fpga value routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        parts = raw.split("_", 1)
        wifi_module = parts[0] if parts and parts[0] else ""
        interface = parts[1] if len(parts) > 1 and parts[1] else ""
        return wifi_module.upper(), interface.upper()

    def _guess_fpga_project(
            self,
            wifi_module: str,
            interface: str,
            main_chip: str = "",
            *,
            customer: str = "",
            product_line: str = "",
            project: str = "",
    ) -> tuple[str, str, str, Optional[dict[str, str]]]:
        """
        Execute the guess fpga project routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        wifi_upper = wifi_module.strip().upper()
        interface_upper = interface.strip().upper()
        chip_upper = main_chip.strip().upper()
        customer_upper = customer.strip().upper()
        product_upper = product_line.strip().upper()
        project_upper = project.strip().upper()
        for customer_name, product_lines in WIFI_PRODUCT_PROJECT_MAP.items():
            if customer_upper and customer_name != customer_upper:
                continue
            for product_name, projects in product_lines.items():
                if product_upper and product_name != product_upper:
                    continue
                for project_name, info in projects.items():
                    if project_upper and project_name != project_upper:
                        continue
                    info_wifi = self._normalize_fpga_token(info.get("wifi_module"))
                    info_if = self._normalize_fpga_token(info.get("interface"))
                    info_chip = self._normalize_fpga_token(info.get("main_chip"))
                    if wifi_upper and info_wifi and info_wifi != wifi_upper:
                        continue
                    if interface_upper and info_if and info_if != interface_upper:
                        continue
                    if chip_upper and info_chip and info_chip != chip_upper:
                        continue
                    return customer_name, product_name, project_name, info
        return "", "", "", None

    def _normalize_fpga_section(self, raw_value: Any) -> dict[str, str]:
        """Normalise FPGA configuration through the config proxy."""
        return self.config_proxy.normalize_fpga_section(raw_value)

    def _normalize_connect_type_section(self, raw_value: Any) -> dict[str, Any]:
        """Normalise connect-type settings through the config proxy."""
        return self.config_proxy.normalize_connect_type_section(raw_value)

    def _normalize_stability_settings(self, raw_value: Any) -> dict[str, Any]:
        """Normalize stability settings using the config proxy implementation."""
        return self.config_proxy.normalize_stability_settings(raw_value)

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

    def _update_fpga_hidden_fields(self) -> None:
        """
        Update the  fpga hidden fields to reflect current data.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        customer = self.fpga_customer_combo.currentText().strip().upper() if hasattr(self,
                                                                                     "fpga_customer_combo") else ""
        product = self.fpga_product_combo.currentText().strip().upper() if hasattr(self, "fpga_product_combo") else ""
        project = self.fpga_project_combo.currentText().strip().upper() if hasattr(self, "fpga_project_combo") else ""
        info: Mapping[str, str] | None = None
        if customer and product and project:
            info = (
                WIFI_PRODUCT_PROJECT_MAP.get(customer, {})
                .get(product, {})
                .get(project, {})
            )
        elif product and project:
            for customer_name, product_lines in WIFI_PRODUCT_PROJECT_MAP.items():
                project_info = product_lines.get(product, {}).get(project)
                if project_info:
                    if not customer:
                        customer = customer_name
                    info = project_info
                    break
        if product and project and info:
            normalized = {
                "customer": customer,
                "product_line": product,
                "project": project,
                "main_chip": self._normalize_fpga_token(info.get("main_chip")),
                "wifi_module": self._normalize_fpga_token(info.get("wifi_module")),
                "interface": self._normalize_fpga_token(info.get("interface")),
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
        self._fpga_details = normalized
        self.config["fpga"] = dict(normalized)

    def on_fpga_customer_changed(self, customer: str) -> None:
        """
        Handle the fpga customer changed event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not hasattr(self, "fpga_product_combo") or not hasattr(self, "fpga_project_combo"):
            return
        current_product = self.fpga_product_combo.currentText().strip().upper()
        customer_upper = customer.strip().upper()
        product_lines = WIFI_PRODUCT_PROJECT_MAP.get(customer_upper, {}) if customer_upper else {}
        product_to_select = current_product if current_product in product_lines else None
        self._refresh_fpga_product_lines(customer, product_to_select, block_signals=True)
        selected_product = self.fpga_product_combo.currentText()
        self.on_fpga_product_line_changed(selected_product)

    def on_fpga_product_line_changed(self, product_line: str) -> None:
        """
        Handle the fpga product line changed event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not hasattr(self, "fpga_project_combo"):
            return
        current_project = self.fpga_project_combo.currentText().strip().upper()
        customer = self.fpga_customer_combo.currentText() if hasattr(self, "fpga_customer_combo") else ""
        projects = WIFI_PRODUCT_PROJECT_MAP.get(customer.strip().upper(), {}).get(product_line.strip().upper(), {})
        project_to_select = current_project if current_project in projects else None
        self._refresh_fpga_projects(customer, product_line, project_to_select, block_signals=True)
        self._update_fpga_hidden_fields()

    def on_fpga_project_changed(self, project: str) -> None:
        """
        Handle the fpga project changed event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self._update_fpga_hidden_fields()

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
        self._update_step_indicator(self.stack.currentIndex())

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
            self._show_info_bar(
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
        """Ensure test_str stability settings require port/mode when AC/STR enabled."""
        config = self.config if isinstance(self.config, dict) else {}
        case_path = config.get("text_case", "")
        case_key = self._script_case_key(case_path)
        if case_key != "test_str":
            return True

        stability_cfg = config.get("stability") if isinstance(config, dict) else {}
        cases_cfg = stability_cfg.get("cases") if isinstance(stability_cfg, dict) else {}
        case_cfg = cases_cfg.get(case_key) if isinstance(cases_cfg, dict) else {}

        errors: list[str] = []
        focus_widget: QWidget | None = None

        def _require(branch: str, label: str) -> None:
            """
            Execute the require routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            nonlocal focus_widget
            branch_cfg = case_cfg.get(branch) if isinstance(case_cfg, dict) else {}
            if not isinstance(branch_cfg, dict) or not branch_cfg.get("enabled"):
                return
            relay_type = str(branch_cfg.get("relay_type") or "usb_relay").strip() or "usb_relay"
            relay_key = relay_type.lower()
            if relay_key == "usb_relay":
                port_value = str(branch_cfg.get("port") or "").strip()
                mode_value = str(branch_cfg.get("mode") or "").strip()
                if not port_value:
                    errors.append(f"{label}: USB power relay port is required.")
                    focus_widget = focus_widget or self.field_widgets.get(
                        f"stability.cases.{case_key}.{branch}.port"
                    )
                if not mode_value:
                    errors.append(f"{label}: Wiring mode is required.")
                    focus_widget = focus_widget or self.field_widgets.get(
                        f"stability.cases.{case_key}.{branch}.mode"
                    )
            elif relay_key == "gwgj-xc3012":
                params = branch_cfg.get("relay_params")
                if isinstance(params, (list, tuple)):
                    items = list(params)
                elif isinstance(params, str):
                    items = [item.strip() for item in params.split(',') if item.strip()]
                else:
                    items = []
                ip_value = str(items[0]).strip() if items else ""
                port_value = None
                if len(items) > 1:
                    try:
                        port_value = int(str(items[1]).strip())
                    except (TypeError, ValueError):
                        port_value = None
                if not ip_value or port_value is None:
                    errors.append(
                        f"{label}: Relay params must include IP and port for GWGJ-XC3012."
                    )
                    focus_widget = focus_widget or self.field_widgets.get(
                        f"stability.cases.{case_key}.{branch}.relay_params"
                    )

        _require("ac", "AC cycle")
        _require("str", "STR cycle")
        if not errors:
            return True

        current_keys = getattr(self, "_current_page_keys", [])
        if isinstance(current_keys, list) and "stability" in current_keys:
            try:
                idx = current_keys.index("stability")
            except ValueError:
                idx = None
            else:
                self.stack.setCurrentIndex(idx)
                self._update_step_indicator(idx)
        if focus_widget is not None and focus_widget.isEnabled():
            focus_widget.setFocus()
            if hasattr(focus_widget, "showPopup"):
                try:
                    focus_widget.showPopup()  # type: ignore[call-arg]
                except Exception:
                    pass

        message = "\n".join(errors)
        try:
            bar = self._show_info_bar(
                "warning",
                "Validation",
                message,
                duration=3200,
            )
            if bar is None:
                raise RuntimeError("InfoBar unavailable")
        except Exception:
            try:
                from PyQt5.QtWidgets import QMessageBox

                QMessageBox.warning(self, "Validation", message)
            except Exception:
                logging.warning("Validation failed: %s", message)
        return False

    def _reset_second_page_inputs(self) -> None:
        """
        Execute the reset second page inputs routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if hasattr(self, "csv_combo"):
            self._set_selected_csv(self.selected_csv_path, sync_combo=True)
            self.csv_combo.setEnabled(bool(self._enable_rvr_wifi))
        else:
            self._set_selected_csv(None, sync_combo=False)

    def _reset_wizard_after_run(self) -> None:
        """
        Execute the reset wizard after run routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.stack.setCurrentIndex(0)
        self._update_step_indicator(0)
        self._update_navigation_state()
        self._reset_second_page_inputs()

    def _on_page_changed(self, index: int) -> None:
        """
        Handle the page changed event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self._update_step_indicator(index)
        self._update_navigation_state()

    def _update_navigation_state(self) -> None:
        """
        Update the  navigation state to reflect current data.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self._sync_run_buttons_enabled()

    def on_next_clicked(self) -> None:
        """
        Handle the next clicked event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self._navigate_to_index(self.stack.currentIndex() + 1)

    def on_previous_clicked(self) -> None:
        """
        Handle the previous clicked event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self._navigate_to_index(self.stack.currentIndex() - 1)

    def _is_performance_case(self, abs_case_path) -> bool:
        """
        判断 abs_case_path 是否位于 test/performance 目录（任何层级都算）。
        不依赖工程根路径，只看路径片段。
        """
        logging.debug("Checking performance case path: %s", abs_case_path)
        if not abs_case_path:
            logging.debug("_is_performance_case: empty path -> False")
            return False
        try:
            from pathlib import Path
            p = Path(abs_case_path).resolve()
            # 检查父链中是否出现 .../test/performance
            for node in (p, *p.parents):
                if node.name == "performance" and node.parent.name == "test":
                    logging.debug("_is_performance_case: True")
                    return True
                logging.debug("_is_performance_case: False")
            return False
        except Exception as e:
            logging.error("_is_performance_case exception: %s", e)
            return False

    def _is_stability_case(self, case_path: str | Path) -> bool:
        """Return True when the case resides under ``test/stability``."""

        if not case_path:
            return False
        try:
            path_obj = case_path if isinstance(case_path, Path) else Path(case_path)
        except (TypeError, ValueError):
            return False
        try:
            resolved = path_obj.resolve()
        except OSError:
            resolved = path_obj
        candidates = [path_obj, resolved]
        for candidate in candidates:
            normalized = candidate.as_posix().replace("\\", "/")
            segments = [seg.lower() for seg in normalized.split("/") if seg]
            for idx in range(len(segments) - 1):
                if segments[idx] == "test" and segments[idx + 1] == "stability":
                    return True
            if normalized.lower().startswith("test/stability/"):
                return True
        return False

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

        # 隐藏非名称列
        self.case_tree.header().hide()
        for col in range(1, self.fs_model.columnCount()):
            self.case_tree.hideColumn(col)

    def _load_config(self) -> dict:
        """Load configuration via the config proxy."""
        return self.config_proxy.load_config()

    def _save_config(self) -> None:
        """Persist configuration changes via the config proxy."""
        self.config_proxy.save_config()

    def _get_application_base(self) -> Path:
        """获取应用根路径"""
        return Path(get_src_base()).resolve()

    def _resolve_case_path(self, path: str | Path) -> Path:
        """将相对用例路径转换为绝对路径"""
        if not path:
            return Path()
        p = Path(path)
        base = Path(self._get_application_base())
        return str(p) if p.is_absolute() else str((base / p).resolve())

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

    def on_connect_type_changed(self, display_text):
        """切换连接方式时，仅展示对应参数组"""
        type_str = self._normalize_connect_type_label(display_text)
        self.adb_group.setVisible(type_str == "Android")
        self.telnet_group.setVisible(type_str == "Linux")
        self._update_android_system_for_connect_type(type_str)
        self._request_rebalance_for_panels(self._dut_panel)

    def _update_android_system_for_connect_type(self, connect_type: str) -> None:
        """
        Update the  android system for connect type to reflect current data.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not hasattr(self, "android_version_combo") or not hasattr(self, "kernel_version_combo"):
            return
        is_adb = connect_type == "Android"
        # Android version selectors are only shown for ADB connections.
        self.android_version_label.setVisible(is_adb)
        self.android_version_combo.setVisible(is_adb)
        # Kernel selector is always visible but toggles between auto-fill and manual modes.
        self.kernel_version_label.setVisible(True)
        self.kernel_version_combo.setVisible(True)
        if is_adb:
            self.kernel_version_combo.setEnabled(False)
            self._apply_android_kernel_mapping()
        else:
            self.kernel_version_combo.setEnabled(True)
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
        if not hasattr(self, "third_party_wait_edit"):
            return
        if allow_wait_edit is None:
            checkbox = getattr(self, "third_party_checkbox", None)
            allow_wait_edit = checkbox.isEnabled() if isinstance(checkbox, QCheckBox) else True
        enable_wait = bool(checked and allow_wait_edit)
        self.third_party_wait_edit.setEnabled(enable_wait)
        if hasattr(self, "third_party_wait_label"):
            self.third_party_wait_label.setEnabled(enable_wait)

    def on_rf_model_changed(self, model_str):
        """
        切换rf_solution.model时，仅展示当前选项参数
        现在只有RS232Board5，如果有别的model，添加隐藏/显示逻辑
        """
        # 当前只有RS232Board5，后续有其它model可以加if-else
        if hasattr(self, "xin_group"):
            self.xin_group.setVisible(model_str == "RS232Board5")
        if hasattr(self, "rc4_group"):
            self.rc4_group.setVisible(model_str == "RC4DAT-8G-95")
        if hasattr(self, "rack_group"):
            self.rack_group.setVisible(model_str == "RADIORACK-4-220")
        if hasattr(self, "lda_group"):
            self.lda_group.setVisible(model_str == "LDA-908V-8")
        self._request_rebalance_for_panels(self._execution_panel)

    # 添加到类里：响应 Tool 下拉，切换子参数可见性
    def on_rvr_tool_changed(self, tool: str):
        """选择 iperf / ixchariot 时，动态显示对应子参数"""
        self.rvr_iperf_group.setVisible(tool == "iperf")
        self.rvr_ix_group.setVisible(tool == "ixchariot")
        self._request_rebalance_for_panels(self._execution_panel)

    def on_serial_enabled_changed(self, text: str):
        """
        Handle the serial enabled changed event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self.serial_cfg_group.setVisible(text == "True")
        self._request_rebalance_for_panels(self._dut_panel)

    def on_router_changed(self, name: str):
        """
        Handle the router changed event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        cfg = self.config.get("router", {})
        addr = cfg.get("address") if cfg.get("name") == name else None
        self.router_obj = get_router(name, addr)
        self.router_addr_edit.setText(self.router_obj.address)
        self.routerInfoChanged.emit()

    def on_router_address_changed(self, text: str) -> None:
        """
        Handle the router address changed event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if self.router_obj is not None:
            self.router_obj.address = text
        self.routerInfoChanged.emit()

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
        """Resolve persisted CSV paths via the RvR Wi-Fi proxy."""
        return _proxy_resolve_csv_config_path(value)

    def _load_csv_selection_from_config(self) -> None:
        """Load CSV selections using the RvR Wi-Fi proxy helpers."""
        _proxy_load_csv_selection_from_config(self)

    def _update_csv_options(self) -> None:
        """Refresh CSV drop-downs via the RvR Wi-Fi proxy."""
        _proxy_update_csv_options(self)

    def _capture_preselected_csv(self) -> None:
        """Cache CSV selections using the RvR Wi-Fi proxy helper."""
        _proxy_capture_preselected_csv(self)

    def _normalize_csv_path(self, path: Any) -> str | None:
        """Normalise CSV paths via the RvR Wi-Fi proxy."""
        return _proxy_normalize_csv_path(path)

    def _relativize_config_path(self, path: Any) -> str:
        """Relativise CSV paths through the RvR Wi-Fi proxy."""
        return _proxy_relativize_config_path(path)

    def _find_csv_index(self, normalized_path: str | None, combo: ComboBox | None = None) -> int:
        """Locate CSV indices using the RvR Wi-Fi proxy helper."""
        return _proxy_find_csv_index(self, normalized_path, combo)

    def _set_selected_csv(self, path: str | None, *, sync_combo: bool = True) -> bool:
        """Update CSV selection via the RvR Wi-Fi proxy implementation."""
        return _proxy_set_selected_csv(self, path, sync_combo=sync_combo)

    def _populate_csv_combo(
            self,
            combo: ComboBox,
            selected_path: str | None,
            *,
            include_placeholder: bool = False,
    ) -> None:
        """Populate CSV combos via the RvR Wi-Fi proxy helper."""
        _proxy_populate_csv_combo(
            self,
            combo,
            selected_path,
            include_placeholder=include_placeholder,
        )

    def _refresh_registered_csv_combos(self) -> None:
        """Refresh CSV combo registrations via the RvR Wi-Fi proxy."""
        _proxy_refresh_registered_csv_combos(self)

    def _load_switch_wifi_entries(self, csv_path: str | None) -> list[dict[str, str]]:
        """Load Wi-Fi CSV rows through the RvR Wi-Fi proxy implementation."""
        return _proxy_load_switch_wifi_entries(self, csv_path)

    def _update_switch_wifi_preview(
            self,
            preview: SwitchWifiCsvPreview | None,
            csv_path: str | None,
    ) -> None:
        """Update Wi-Fi preview widgets via the RvR Wi-Fi proxy."""
        _proxy_update_switch_wifi_preview(self, preview, csv_path)

    def _update_rvr_nav_button(self) -> None:
        """Update the RVR navigation button using the proxy helper."""
        _proxy_update_rvr_nav_button(self)

    def _open_rvr_wifi_config(self) -> None:
        """Open the RVR Wi-Fi configuration page via the proxy helper."""
        _proxy_open_rvr_wifi_config(self)

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

    def _active_case_type(self) -> str:
        """Return the current case type identifier used for section selection."""
        if getattr(self, "_current_case_path", ""):
            return self._script_case_key(self._current_case_path)
        return "default"

    def _build_registered_sections(self) -> set[str]:
        """Instantiate registered sections and build their widgets."""
        case_type = self._active_case_type()
        tags: set[str] = set()
        sections = build_sections(self, case_type, tags)
        self._section_context = SectionContext(case_type, tags)
        self._section_instances = {section.section_id: section for section in sections}
        for section in sections:
            section.build(self.config)
        return set(self._section_instances.keys())

    def render_all_fields(self):
        """自动渲染配置字段，支持 LineEdit / ComboBox（可扩展 Checkbox）。"""
        self._dut_groups.clear()
        self._other_groups.clear()
        defaults_for_dut = {
            "software_info": {},
            "hardware_info": {},
            "android_system": {},
        }
        for _key, _default in defaults_for_dut.items():
            existing = self.config.get(_key)
            if not isinstance(existing, dict):
                self.config[_key] = _default.copy()
            else:
                self.config[_key] = dict(existing)

        def _coerce_debug_flag(value) -> bool:
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)

        def _normalize_debug_section(raw_value) -> dict[str, bool]:
            if isinstance(raw_value, dict):
                normalized = dict(raw_value)
            else:
                normalized = {"database_mode": raw_value}
            for option in ("database_mode", "skip_router", "skip_corner_rf"):
                normalized[option] = _coerce_debug_flag(normalized.get(option))
            return normalized

        self.config["debug"] = _normalize_debug_section(self.config.get("debug"))
        self.config["connect_type"] = self._normalize_connect_type_section(self.config.get("connect_type"))
        linux_cfg = self.config["connect_type"].get("Linux")
        if isinstance(linux_cfg, dict) and "kernel_version" in linux_cfg:
            self.config.setdefault("android_system", {})["kernel_version"] = linux_cfg.pop("kernel_version")
        self.config["fpga"] = self._normalize_fpga_section(self.config.get("fpga"))
        self.config["stability"] = self._normalize_stability_settings(
            self.config.get("stability")
        )
        handled_section_ids = self._build_registered_sections()
        for key, value in self.config.items():
            if key in handled_section_ids or key == "stability":
                continue
            if key in ["csv_path", TOOL_SECTION_KEY]:
                continue
            group, vbox = build_groupbox(key)
            edit = LineEdit(self)
            edit.setText(str(value) if value is not None else "")
            vbox.addWidget(edit)
            self._register_group(key, group, self._is_dut_key(key))
            self.field_widgets[key] = edit

        self._build_duration_group()

    def _build_network_group(self, value: Mapping[str, Any] | None) -> None:
        """Create the router configuration group via the proxy helper."""
        _proxy_build_network_group(self, value)

    def _build_traffic_group(self, value: Mapping[str, Any] | None) -> None:
        """Create serial/traffic controls via the proxy helper."""
        _proxy_build_traffic_group(self, value)

    def _build_duration_group(self) -> None:
        """Attach duration/checkpoint groups using the proxy helpers."""
        _proxy_build_duration_group(self)


    def _ensure_turntable_inputs_exclusive(self, source: str | None) -> None:
        """
        Execute the ensure turntable inputs exclusive routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not hasattr(self, "turntable_static_db_edit") or not hasattr(
                self, "turntable_target_rssi_edit"
        ):
            return
        static_text = self.turntable_static_db_edit.text().strip()
        target_text = self.turntable_target_rssi_edit.text().strip()
        if not static_text or not target_text:
            return

        if source == "target":
            cleared = self.turntable_static_db_edit
            focus_widget = self.turntable_target_rssi_edit
        elif source == "static":
            cleared = self.turntable_target_rssi_edit
            focus_widget = self.turntable_static_db_edit
        else:
            cleared = self.turntable_target_rssi_edit
            focus_widget = None

        with QSignalBlocker(cleared):
            cleared.clear()

        self._show_turntable_conflict_warning(focus_widget)

    def _on_turntable_model_changed(self, model: str) -> None:
        """
        Handle the turntable model changed event triggered by user interaction.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if not hasattr(self, "turntable_ip_edit") or not hasattr(
                self, "turntable_ip_label"
        ):
            return
        requires_ip = model == TURN_TABLE_MODEL_OTHER
        self.turntable_ip_label.setVisible(requires_ip)
        self.turntable_ip_edit.setVisible(requires_ip)
        self.turntable_ip_edit.setEnabled(requires_ip)

    def _build_duration_control_group(
            self, data: Mapping[str, Any] | None
    ) -> QGroupBox:
        """Construct the duration control group via the proxy helper."""
        return _proxy_build_duration_control_group(self, data)

    def _build_check_point_group(
            self, data: Mapping[str, Any] | None
    ) -> QGroupBox:
        """Construct the checkpoint selection group via the proxy helper."""
        return _proxy_build_check_point_group(self, data)

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

        self._show_turntable_conflict_warning(focus_widget)

    def _show_turntable_conflict_warning(
            self, focus_widget: QWidget | None
    ) -> None:
        """
        Execute the show turntable conflict warning routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if focus_widget is None or not focus_widget.hasFocus():
            return
        message = (
            "Static dB and Target RSSI cannot be configured at the same time. "
            "The other field has been cleared."
        )
        try:
            bar = self._show_info_bar(
                "warning",
                "Configuration Conflict",
                message,
                duration=2600,
            )
            if bar is None:
                raise RuntimeError("InfoBar unavailable")
        except Exception:
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Configuration Conflict", message)

    def populate_case_tree(self, root_dir):
        """
        遍历 test 目录，只将 test_ 开头的 .py 文件作为节点加入树结构。
        其它 py 文件不显示。
        """
        from PyQt5.QtGui import QStandardItemModel, QStandardItem
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['Pls select test case '])  # 可选，设置表头显示

        # 正确设置根节点为 'test' 或实际目录名
        root_item = QStandardItem(os.path.basename(root_dir))
        root_item.setData(root_dir)

        def add_items(parent_item, dir_path):
            """
            Execute the add items routine.

            This method encapsulates the logic necessary to perform its function.
            Refer to the implementation for details on parameters and return values.
            """
            for fname in sorted(os.listdir(dir_path)):
                logging.debug("fname %s", fname)
                if fname == '__pycache__' or fname.startswith('.'):
                    continue
                path = os.path.join(dir_path, fname)
                if os.path.isdir(path):
                    dir_item = QStandardItem(fname)
                    dir_item.setData(path)
                    parent_item.appendRow(dir_item)
                    add_items(dir_item, path)
                elif os.path.isfile(path):
                    file_item = QStandardItem(fname)
                    file_item.setData(path)
                    parent_item.appendRow(file_item)

        add_items(root_item, root_dir)
        model.appendRow(root_item)
        self.case_tree.setModel(model)
        # 展开根节点
        self.case_tree.expand(model.index(0, 0))

    def on_case_tree_clicked(self, proxy_idx):
        """
        proxy_idx: 用户在界面点击到的索引（始终是代理模型的）
        """
        model = self.case_tree.model()

        # —— 用源索引只负责取真实文件路径 ——
        source_idx = (
            model.mapToSource(proxy_idx)
            if isinstance(model, QSortFilterProxyModel) else proxy_idx
        )
        path = self.fs_model.filePath(source_idx)
        base = Path(self._get_application_base())
        try:
            display_path = os.path.relpath(path, base)
        except ValueError:
            display_path = path
        logging.debug("on_case_tree_clicked path=%s display=%s", path, display_path)
        logging.debug("on_case_tree_clicked is_performance=%s", self._is_performance_case(path))
        # ---------- 目录：只负责展开/折叠 ----------
        if os.path.isdir(path):
            if self.case_tree.isExpanded(proxy_idx):
                self.case_tree.collapse(proxy_idx)
            else:
                self.case_tree.expand(proxy_idx)
            self.set_fields_editable(set())
            return

        # ---------- 非 test_*.py 直接禁用 ----------
        if not (os.path.isfile(path)
                and os.path.basename(path).startswith("test_")
                and path.endswith(".py")):
            self.set_fields_editable(set())
            return

        normalized_display = Path(display_path).as_posix() if display_path else ""
        self._update_test_case_display(normalized_display)

        # ---------- 有效用例 ----------
        if self._refreshing:
            self._pending_path = path
            return
        self.get_editable_fields(path)

    def _compute_editable_info(self, case_path) -> EditableInfo:
        """根据用例名与路径返回可编辑字段以及相关 UI 使能状态"""
        basename = os.path.basename(case_path)
        logging.debug("testcase name %s", basename)
        logging.debug("_compute_editable_info case_path=%s basename=%s", case_path, basename)
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
        # 永远让 connect_type 可编辑
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
        if basename == "test_wifi_peak_throughput.py":
            info.fields |= peak_keys
        if self._is_performance_case(case_path):
            info.fields |= rvr_keys
            info.enable_csv = True
            info.enable_rvr_wifi = True
        if "rvo" in basename:
            info.fields |= {
                f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_MODEL}",
                f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_IP_ADDRESS}",
                f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_STEP}",
                f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_STATIC_DB}",
                f"{TURN_TABLE_SECTION_KEY}.{TURN_TABLE_FIELD_TARGET_RSSI}",
            }
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
        if self._is_stability_case(case_path):
            info.fields |= {
                "stability.duration_control.loop",
                "stability.duration_control.duration_hours",
                "stability.duration_control.exitfirst",
                "stability.duration_control.retry_limit",
                "stability.check_point.ping",
                "stability.check_point.ping_targets",
            }
        case_key = self._script_case_key(case_path)
        entry = self._script_groups.get(case_key)
        if entry is not None:
            info.fields |= entry.field_keys
        # 如果你需要所有字段都可编辑，直接 return EditableInfo(set(self.field_widgets.keys()), True, True)
        return info

    def _apply_editable_info(self, info: EditableInfo | None) -> None:
        """
        Execute the apply editable info routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        if info is None:
            fields: set[str] = set()
            enable_csv = False
            enable_rvr_wifi = False
        else:
            fields = set(info.fields)
            enable_csv = info.enable_csv
            enable_rvr_wifi = info.enable_rvr_wifi
        snapshot = EditableInfo(fields=fields, enable_csv=enable_csv, enable_rvr_wifi=enable_rvr_wifi)
        self._last_editable_info = snapshot
        self.set_fields_editable(snapshot.fields)
        self._enable_rvr_wifi = snapshot.enable_rvr_wifi
        if not snapshot.enable_rvr_wifi:
            self._router_config_active = False
        if hasattr(self, "csv_combo"):
            if snapshot.enable_csv:
                self.csv_combo.setEnabled(True)
                self._set_selected_csv(self.selected_csv_path, sync_combo=True)
            else:
                # self._set_selected_csv(None, sync_combo=True)
                self.csv_combo.setEnabled(False)
        else:
            if not snapshot.enable_csv:
                self._set_selected_csv(None, sync_combo=False)
        self._update_rvr_nav_button()

    def _restore_editable_state(self) -> None:
        """
        Execute the restore editable state routine.

        This method encapsulates the logic necessary to perform its function.
        Refer to the implementation for details on parameters and return values.
        """
        self._apply_editable_info(self._last_editable_info)

    def get_editable_fields(self, case_path) -> EditableInfo:
        """选中用例后控制字段可编辑性并返回相关信息"""
        logging.debug("get_editable_fields case_path=%s", case_path)
        if self._refreshing:
            # 极少见：递归进入，直接丢弃
            logging.debug("get_editable_fields: refreshing, return empty")
            return EditableInfo()

        # ---------- 进入刷新 ----------
        self._refreshing = True
        self.case_tree.setEnabled(False)  # 锁定用例树
        self.setUpdatesEnabled(False)  # 暂停全局重绘

        try:
            self._update_script_config_ui(case_path)
            info = self._compute_editable_info(case_path)
            logging.debug("get_editable_fields enable_csv=%s", info.enable_csv)
            if info.enable_csv and not hasattr(self, "csv_combo"):
                info.enable_csv = False
            self._apply_editable_info(info)
            page_keys = self._determine_pages_for_case(case_path, info)
            self._set_available_pages(page_keys)
        finally:
            # ---------- 刷新结束 ----------
            self.setUpdatesEnabled(True)
            self.case_tree.setEnabled(True)
            self._refreshing = False

        main_window = self.window()
        if hasattr(main_window, "setCurrentIndex"):
            logging.debug("get_editable_fields: before switch to case_config_page")
            main_window.setCurrentIndex(main_window.case_config_page)
            logging.debug("get_editable_fields: after switch to case_config_page")
        if not hasattr(self, "csv_combo"):
            logging.debug("csv_combo disabled")
        # 若用户在刷新过程中又点了别的用例，延迟 0 ms 处理它
        if self._pending_path:
            path = self._pending_path
            self._pending_path = None
            QTimer.singleShot(0, lambda: self.get_editable_fields(path))
        return info

    def set_fields_editable(self, editable_fields: set[str]) -> None:
        """批量更新字段的可编辑状态；DUT 区域始终保持可操作"""
        self.setUpdatesEnabled(False)
        try:
            always_enabled_roots = {"debug"}
            for key, widget in self.field_widgets.items():
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
                self.on_third_party_toggled(self.third_party_checkbox.isChecked(), allow_wait)
            self._refresh_script_section_states()
        finally:
            self.setUpdatesEnabled(True)
            self.update()

    def lock_for_running(self, locked: bool) -> None:

        """Enable or disable widgets while a test run is active."""
        self.case_tree.setEnabled(not locked)
        self._run_locked = locked
        self._sync_run_buttons_enabled()
        if locked:
            for w in self.field_widgets.values():
                w.setEnabled(False)
            if hasattr(self, "csv_combo"):
                self.csv_combo.setEnabled(False)
        else:
            self._restore_editable_state()
        if not locked:
            self._update_navigation_state()

    def on_csv_activated(self, index: int) -> None:

        """Reload CSV data even if the same entry is activated again."""
        logging.debug("on_csv_activated index=%s", index)
        self.on_csv_changed(index, force=True)

    def on_csv_changed(self, index: int, force: bool = False) -> None:

        """Store the selected CSV path and emit a change signal."""
        if index < 0:
            self._set_selected_csv(None, sync_combo=False)
            return
        # 明确使用 UserRole 获取数据，避免在不同 Qt 版本下默认角色不一致
        data = self.csv_combo.itemData(index)
        logging.debug("on_csv_changed index=%s data=%s", index, data)
        new_path = self._normalize_csv_path(data)
        if not force and new_path == self.selected_csv_path:
            return
        self._set_selected_csv(new_path, sync_combo=False)
        logging.debug("selected_csv_path=%s", self.selected_csv_path)
        self.csvFileChanged.emit(self.selected_csv_path or "")

    def on_run(self):
        """Trigger the run workflow via the run proxy implementation."""
        _proxy_on_run(self)
