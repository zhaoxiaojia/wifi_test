"""View + page implementation for the Config sidebar (DUT/Execution/Stability)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from PyQt5.QtCore import (
    Qt,
    QTimer,
    pyqtSignal,
    QPropertyAnimation,
    QParallelAnimationGroup,
    QObject,
    pyqtProperty,
)
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QLabel,
)
from qfluentwidgets import CardWidget, ComboBox, PushButton, ScrollArea, FluentIcon, TreeView

from src.ui.controller.config_ctl import ConfigController
from src.ui.view.common import ConfigGroupPanel, EditableInfo, ScriptConfigEntry, PAGE_CONTENT_MARGIN
from src.ui.view.theme import (
    CASE_TREE_FONT_SIZE_PX,
    apply_font_and_selection,
    apply_theme,
    apply_settings_tab_label_style,
)
from src.ui.view.config.actions import (
    handle_config_event,
    init_fpga_dropdowns,
    refresh_config_page_controls,
)
from src.ui.view.config.config_str import (
    create_test_str_config_entry_from_schema,
    create_test_switch_wifi_config_entry_from_schema,
    initialize_script_config_groups,
)
from src.util.constants import (
    DEFAULT_ANDROID_VERSION_CHOICES,
    DEFAULT_KERNEL_VERSION_CHOICES,
)
from src.tools.router_tool.router_factory import router_list, get_router
from src.ui.controller.case_ctl import _register_switch_wifi_csv_combo as _reg_sw_csv


class _RowHeightWrapper(QObject):
    """
    Helper object that bridges a single index's row height to a Qt property.

    The wrapper allows using :class:`QPropertyAnimation` on a per-index basis.
    It stores and retrieves heights in the parent tree's private height map
    (``tree._row_heights``), then triggers geometry updates on change.
    """

    def __init__(self, tree: "AnimatedTreeView", index) -> None:
        super().__init__(tree)
        self._tree = tree
        self._index = index

    def _set_height(self, height: int) -> None:
        self._tree._row_heights[self._index] = height
        self._tree.updateGeometries()

    def _get_height(self) -> int:
        return self._tree._row_heights.get(self._index, 0)

    #: Qt property used by QPropertyAnimation.
    height = pyqtProperty(int, fset=_set_height, fget=_get_height)


class AnimatedTreeView(TreeView):
    """
    A TreeView with expand animation for child rows.

    Behavior
    --------
    - When expanding an index, the control pre-expands the node (so children
      exist), then animates each direct child's row height from 0 to its native
      size hint using a parallel animation group.
    - While the animation runs, :meth:`indexRowSizeHint` serves the temporary
      heights from ``_row_heights`` so the viewport progressively reveals rows.
    - After the animation finishes, temporary overrides are cleared, updates are
      re-enabled, and the viewport is repainted once.
    """

    ANIMATION_DURATION = 180  # ms

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._row_heights: dict[object, int] = {}

    def indexRowSizeHint(self, index):  # noqa: N802 (Qt naming convention)
        """Return row height for ``index`` honoring active animations."""
        return self._row_heights.get(index, super().indexRowSizeHint(index))

    def setExpanded(self, index, expand):  # noqa: D401, N802
        """Reimplemented to animate child rows on expand."""
        model = self.model()
        if expand and model is not None:
            self.setUpdatesEnabled(False)
            super().setExpanded(index, expand)
            group = QParallelAnimationGroup(self)
            for row in range(model.rowCount(index)):
                child = model.index(row, 0, index)
                target = super().indexRowSizeHint(child)
                self._row_heights[child] = 0
                wrapper = _RowHeightWrapper(self, child)
                anim = QPropertyAnimation(wrapper, b"height", self)
                anim.setDuration(self.ANIMATION_DURATION)
                anim.setStartValue(0)
                anim.setEndValue(target)
                group.addAnimation(anim)

            def _on_finished() -> None:
                for row in range(model.rowCount(index)):
                    child = model.index(row, 0, index)
                    self._row_heights.pop(child, None)
                self.setUpdatesEnabled(True)
                self.viewport().update()

            group.finished.connect(_on_finished)
            group.start(QPropertyAnimation.DeleteWhenStopped)
        else:
            super().setExpanded(index, expand)


class _ConfigTabLabel(QLabel):
    """Clickable label used for DUT/Execution/Stability tabs."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ConfigView(CardWidget):
    """Pure UI view for the Config page (no business logic)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        apply_theme(self)

        # Left/right splitter
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)

        # Left: case tree
        self.case_tree = AnimatedTreeView(self)
        apply_theme(self.case_tree)
        apply_font_and_selection(self.case_tree, size_px=CASE_TREE_FONT_SIZE_PX)
        self.splitter.addWidget(self.case_tree)

        # Right: scroll area with stacked pages
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = scroll_area

        container = QWidget()
        right = QVBoxLayout(container)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(10)

        # Track which logical pages are currently available
        self._current_page_keys: list[str] = []

        # Simple tab row for DUT / Execution / Stability
        self._page_label_map: dict[str, str] = {
            "dut": "DUT",
            "execution": "Execution",
            "stability": "Stability",
        }
        self._page_buttons: dict[str, _ConfigTabLabel] = {}
        tabs_row = QHBoxLayout()
        tabs_row.setContentsMargins(PAGE_CONTENT_MARGIN, PAGE_CONTENT_MARGIN, PAGE_CONTENT_MARGIN, 0)
        tabs_row.setSpacing(8)
        for key in ("dut", "execution", "stability"):
            lbl = _ConfigTabLabel(self._page_label_map[key], self)
            apply_settings_tab_label_style(lbl, active=(key == "dut"))

            def _make_handler(page_key: str) -> Any:
                def _handler() -> None:
                    page = self.parent()
                    # Climb parents until we reach an object with a controller.
                    while page is not None and not hasattr(page, "config_ctl"):
                        page = page.parent()
                    if page is not None:
                        handle_config_event(page, "settings_tab_clicked", key=page_key)

                return _handler

            lbl.clicked.connect(_make_handler(key))
            self._page_buttons[key] = lbl
            tabs_row.addWidget(lbl)
        tabs_row.addStretch(1)
        right.addLayout(tabs_row)

        self.stack = QStackedWidget(self)
        right.addWidget(self.stack, 1)

        self._page_panels: dict[str, ConfigGroupPanel] = {
            "dut": ConfigGroupPanel(self),
            "execution": ConfigGroupPanel(self),
            "stability": ConfigGroupPanel(self),
        }
        self._page_widgets: dict[str, QWidget] = {}
        self._run_buttons: list[PushButton] = []

        for key in ("dut", "execution", "stability"):
            panel = self._page_panels[key]
            page = QWidget()
            page.setObjectName(f"config_{key}_page")
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
            )
            page_layout.setSpacing(PAGE_CONTENT_MARGIN)
            page_layout.addWidget(panel, 1)
            run_btn = self._create_run_button(page)
            page_layout.addWidget(run_btn, 0)
            self._page_widgets[key] = page

        # Initialise stack and step view with the default page selection.
        self.set_available_pages(["dut"])

        scroll_area.setWidget(container)
        self.splitter.addWidget(scroll_area)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.addWidget(self.splitter)

    def _create_run_button(self, parent: QWidget) -> PushButton:
        """Create a Run button for the page (UI only)."""
        button = PushButton("Run", parent)
        button.setIcon(FluentIcon.PLAY)
        if hasattr(button, "setUseRippleEffect"):
            button.setUseRippleEffect(True)
        if hasattr(button, "setUseStateEffect"):
            button.setUseStateEffect(True)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._run_buttons.append(button)
        return button

    # Public API used by controllers
    # ------------------------------------------------------------------

    def set_available_pages(self, page_keys: Sequence[str]) -> None:
        """Show the given logical pages in the stacked widget."""
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

        # Rebuild stack order to match normalized keys.
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
        for key in normalized:
            self.stack.addWidget(self._page_widgets[key])

        self._current_page_keys = normalized

        # Update tab visibility based on available pages.
        for key, lbl in self._page_buttons.items():
            lbl.setVisible(key in normalized)

        # Preserve current page when possible.
        target_index = 0
        if current_key in normalized:
            target_index = normalized.index(current_key)
        self.stack.setCurrentIndex(target_index)
        self._update_tab_checked(target_index)

    # ------------------------------------------------------------------
    # Tab helpers
    # ------------------------------------------------------------------

    def _update_tab_checked(self, index: int) -> None:
        """Update which tab button appears active."""
        if not (0 <= index < len(self._current_page_keys)):
            return
        active_key = self._current_page_keys[index]
        for key, lbl in self._page_buttons.items():
            apply_settings_tab_label_style(lbl, active=(key == active_key))

    def set_current_page(self, key: str) -> None:
        """Public helper to switch to a logical page key."""
        if key not in self._current_page_keys:
            return
        index = self._current_page_keys.index(key)
        self.stack.setCurrentIndex(index)
        self._update_tab_checked(index)


class CaseConfigPage(ConfigView):
    """Controller+view wrapper for the Config page.

    This merges the previous :class:`CaseConfigPage` implementation from
    ``src.ui.case_config_page`` with :class:`ConfigView` so that the page
    can be used directly without a separate wrapper module.
    """

    routerInfoChanged = pyqtSignal()
    csvFileChanged = pyqtSignal(str)

    def __init__(self, on_run_callback) -> None:
        super().__init__(parent=None)
        self.setObjectName("caseConfigPage")
        self.on_run_callback = on_run_callback

        # Controller responsible for config lifecycle/normalisation.
        self.config_ctl = ConfigController(self)

        # Load the persisted tool configuration and restore CSV selection.
        self.config: dict[str, Any] = self.config_ctl.load_initial_config()

        # Transient state flags used during refreshes and selections.
        self.selected_csv_path: str | None = None
        self._refreshing = False
        self._pending_path: str | None = None

        # Mapping from config field keys (e.g. "android_system.version") to widgets.
        self.field_widgets: dict[str, QWidget] = {}

        # Mapping from logical UI identifiers (config_panel_group_field_type) to widgets.
        self.config_controls: dict[str, QWidget] = {}

        self._duration_control_group: QGroupBox | None = None
        self._check_point_group: QGroupBox | None = None

        self.router_obj: Any | None = None
        self._enable_rvr_wifi: bool = False
        self._router_config_active: bool = False
        self._run_locked: bool = False
        self._locked_fields: set[str] | None = None
        self._current_case_path: str = ""
        self._last_editable_info: EditableInfo | None = None

        # Switch‑Wi‑Fi CSV combo management.
        self._switch_wifi_csv_combos: list[ComboBox] = []
        self.register_switch_wifi_csv_combo = lambda combo: _reg_sw_csv(self, combo)

        # Track Android/kernel version options.
        self._android_versions = list(DEFAULT_ANDROID_VERSION_CHOICES)
        self._kernel_versions = list(DEFAULT_KERNEL_VERSION_CHOICES)

        # Logical page tracking from the controller perspective.
        self._current_page_keys = ["dut"]

        self._script_config_factories: dict[
            str, Callable[[Any, str, str, Mapping[str, Any]], ScriptConfigEntry]
        ] = {
            "test/stability/test_str.py": create_test_str_config_entry_from_schema,
            "test/stability/test_switch_wifi.py": create_test_switch_wifi_config_entry_from_schema,
        }
        self._script_groups: dict[str, ScriptConfigEntry] = {}
        self._active_script_case: str | None = None

        self._config_panels = tuple(self._page_panels[key] for key in ("dut", "execution", "stability"))

        # Containers for groups discovered from the YAML schema.
        self._dut_groups: dict[str, QWidget] = {}
        self._other_groups: dict[str, QWidget] = {}

        # Render form fields from YAML and initialise script groups.
        refresh_config_page_controls(self)
        initialize_script_config_groups(self)

        # Initialise case tree using src/test as root (non-fatal on failure).
        try:
            base = Path(self.config_ctl.get_application_base())
            test_root = base / "test"
            if test_root.exists():
                self.config_ctl.init_case_tree(test_root)
        except Exception:
            pass

        # Apply initial UI rules/state.
        try:
            from src.ui.view.config.actions import apply_config_ui_rules

            apply_config_ui_rules(self)
        except Exception:
            pass

        # CSV/router updates.
        self.routerInfoChanged.connect(self.config_ctl.update_csv_options)
        self.config_ctl.update_csv_options()

        # Connect signals after UI ready.
        self.case_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        QTimer.singleShot(0, lambda: self.config_ctl.get_editable_fields(""))

    # ------------------------------------------------------------------
    # Helpers used by controller / actions
    # ------------------------------------------------------------------

    def _determine_pages_for_case(self, case_path: str, info: EditableInfo) -> list[str]:
        """Delegate page-key computation to the config controller."""
        return self.config_ctl.determine_pages_for_case(case_path, info)

    def set_fields_editable(self, fields: set[str]) -> None:
        """Enable or disable config widgets based on the given editable field keys."""
        from src.ui.view.config.actions import set_fields_editable as _set_fields

        _set_fields(self, fields)


__all__ = ["ConfigView", "CaseConfigPage"]
