"""View + page implementation for the Config sidebar (DUT/Execution/Stability)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, Dict, List

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
    apply_ui,
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
                    # Find the owning config page that holds the controller.
                    page = self
                    while page is not None and not hasattr(page, "config_ctl"):
                        page = page.parent()
                    # Basic debug output to help analyse tab behaviour.
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
        # Backward-compatible attributes expected by existing actions/helpers.
        # These aliases allow refresh_config_page_controls (and related helpers)
        # to treat the three panels as dedicated attributes while the view
        # internally tracks them in a dictionary.
        self._dut_panel = self._page_panels["dut"]
        self._execution_panel = self._page_panels["execution"]
        self._stability_panel = self._page_panels["stability"]
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
        # Keep tree (left) : form (right) width ratio close to 3:7.
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 7)

        # Flag used by resizeEvent to apply an initial 3:7 ratio once.
        self._splitter_initialized = False

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

    # ------------------------------------------------------------------
    # Size handling
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:  # noqa: D401  (Qt override)
        """Reimplemented to apply an initial tree/form ratio once.

        Qt's splitter layout can override :meth:`setSizes` during the
        first layout pass. To keep behaviour consistent with the legacy
        implementation (approximately 3:7 for tree vs. config form),
        this override applies a 30%/70% split the first time the view
        receives a resize event, then lets user resizing take over.
        """
        super().resizeEvent(event)
        if getattr(self, "_splitter_initialized", False):
            return
        if not hasattr(self, "splitter") or self.splitter.count() < 2:
            return
        total = max(self.splitter.width(), 10)
        left = max(int(total * 0.25), 1)
        right = max(total - left, 1)
        self.splitter.setSizes([left, right])
        sizes = self.splitter.sizes()
        span = max(sum(sizes), 1)
        ratio = sizes[0] / span
        self._splitter_initialized = True


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

        # Backward-compatible attribute: older helpers expect a page.view
        # pointing at the ConfigView instance used for tab switching.
        self.view = self

        # Controller responsible for config lifecycle/normalisation.
        self.config_ctl = ConfigController(self)

        # Load the persisted tool configuration and restore CSV selection.
        # load_initial_config populates ``self.config`` and, when possible,
        # initialises ``self.selected_csv_path`` from the stored csv_path.
        self.config: dict[str, Any] = self.config_ctl.load_initial_config()

        # Transient state flags used during refreshes and selections.
        # Do not clobber selected_csv_path here so that any value restored
        # from config remains available for initial combo population.
        self.selected_csv_path: str | None = getattr(self, "selected_csv_path", None)
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
        # Preserve any _current_case_path set by the controller during
        # load_initial_config; default to empty string otherwise.
        self._current_case_path: str = getattr(self, "_current_case_path", "")
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

        # ------------------------------------------------------------------
        # Simple rules integration
        #
        # Build a field map that maps dotted field identifiers to widgets.
        # This map is used by the simple rule engine (see src/ui/model/rules.py)
        # to look up widgets and apply actions such as show/hide and enable/disable.
        # The field_widgets dictionary is populated by refresh_config_page_controls.
        self._field_map = getattr(self, "field_widgets", {}) or {}

        # Connect triggers for custom simple rules.  Only a subset of fields
        # currently participate in the simple rule engine, so connections are
        # registered conditionally.  See _connect_simple_rules for details.
        self._connect_simple_rules()

        # Initialise case tree using src/test as root (non-fatal on failure).
        try:
            base = Path(self.config_ctl.get_application_base())
            test_root = base / "test"
            if test_root.exists():
                self.config_ctl.init_case_tree(test_root)
        except Exception:
            pass

        # Apply initial UI rules/state via the unified rule engine.
        try:
            from src.ui.model.rules import evaluate_all_rules

            evaluate_all_rules(self, None)
        except Exception:
            pass

        # CSV/router updates.
        self.routerInfoChanged.connect(self.config_ctl.update_csv_options)
        self.config_ctl.update_csv_options()

        # Connect signals after UI ready.
        self.case_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        QTimer.singleShot(
            0,
            lambda: apply_ui(self, getattr(self, "_current_case_path", "") or ""),
        )

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

    # ------------------------------------------------------------------
    # Simple rule integration methods
    # ------------------------------------------------------------------

    def _connect_simple_rules(self) -> None:
        """
        Wire up field change signals to the simple rule engine.

        The simple rule system defined in :mod:`src.ui.model.rules` needs
        to know when certain fields change in order to evaluate and apply
        dynamic UI effects.  This helper inspects the custom rule registry
        and connects the appropriate Qt signals for each trigger field.

        For each rule in ``CUSTOM_SIMPLE_UI_RULES``, this method looks up
        the corresponding widget in ``self._field_map``.  Depending on the
        widget type, it connects a change signal to ``self.on_field_changed``
        with the rule's trigger field name.  This ensures that when a user
        changes the field in the UI, the simple rule engine is invoked.
        """
        try:
            from src.ui.model.rules import CUSTOM_SIMPLE_UI_RULES  # type: ignore
        except Exception:
            CUSTOM_SIMPLE_UI_RULES = []  # type: ignore
        for rule in CUSTOM_SIMPLE_UI_RULES:
            field_id = getattr(rule, "trigger_field", None)
            if not field_id:
                continue
            widget = self._field_map.get(field_id)
            if widget is None:
                continue
            try:
                # Combo boxes emit currentTextChanged when the selection changes.
                if hasattr(widget, "currentTextChanged"):
                    widget.currentTextChanged.connect(
                        lambda value, fid=field_id: self.on_field_changed(fid, value)
                    )
                # Checkboxes emit toggled when the checked state changes.
                elif hasattr(widget, "toggled"):
                    widget.toggled.connect(
                        lambda value, fid=field_id: self.on_field_changed(fid, value)
                    )
                # Line edits emit textChanged for free‑form input.
                elif hasattr(widget, "textChanged"):
                    widget.textChanged.connect(
                        lambda value, fid=field_id: self.on_field_changed(fid, value)
                    )
            except Exception:
                # Ignore connection errors; missing signals simply mean the rule
                # cannot be triggered automatically.
                continue
        # Evaluate simple rules for current values on initialisation.
        # In particular, rules that depend on default configuration values
        # should apply their effects immediately so the UI reflects the
        # current config state.
        for rule in CUSTOM_SIMPLE_UI_RULES:
            fid = getattr(rule, "trigger_field", None)
            if fid and fid in self._field_map:
                widget = self._field_map[fid]
                # Determine the current value for the field based on widget type.
                try:
                    if hasattr(widget, "isChecked"):
                        current_value = bool(widget.isChecked())
                    elif hasattr(widget, "currentText"):
                        current_value = str(widget.currentText())
                    elif hasattr(widget, "text"):
                        current_value = str(widget.text())
                    else:
                        current_value = None
                    self.on_field_changed(fid, current_value)
                except Exception:
                    continue

    def on_field_changed(self, field_id: str, value: Any) -> None:
        """
        Respond to a change in a field value by evaluating all UI rules.

        This delegates to :func:`evaluate_all_rules` in the rules module so
        that all simple per-field rules are applied through a single entry
        point.
        """
        try:
            from src.ui.model.rules import evaluate_all_rules  # type: ignore
        except Exception:
            return
        evaluate_all_rules(self, field_id)

    def _collect_values(self) -> Dict[str, Any]:
        """
        Return a mapping of all field identifiers to their current values.

        This helper inspects every widget in ``self._field_map`` and extracts
        its current value based on common widget APIs.  Checkboxes yield
        boolean values, combo boxes and other widgets yield their current
        textual representation, and line edits return their plain text.
        """
        values: Dict[str, Any] = {}
        for key, widget in (self._field_map or {}).items():
            try:
                # QCheckBox has isChecked
                if hasattr(widget, "isChecked"):
                    values[key] = bool(widget.isChecked())
                # QSpinBox / QDoubleSpinBox have value() but treat as numeric
                elif hasattr(widget, "value") and not hasattr(widget, "currentText"):
                    values[key] = widget.value()
                # ComboBox (and similar) have currentText
                elif hasattr(widget, "currentText"):
                    values[key] = str(widget.currentText())
                # LineEdit (and similar) have text
                elif hasattr(widget, "text"):
                    values[key] = str(widget.text())
            except Exception:
                values[key] = None
        return values

    # ------------------------------------------------------------------
    # UIAdapter methods for simple rule engine
    # ------------------------------------------------------------------
    def _get_field_widget(self, field_id: str) -> QWidget | None:
        """Return the widget associated with a dotted field identifier."""
        return (self._field_map or {}).get(field_id)

    def show(self, field_id: str) -> None:  # noqa: D401 (UIAdapter)
        widget = self._get_field_widget(field_id)
        if widget is None:
            return
        try:
            widget.setVisible(True)
            # Also show the label when the widget lives in a QFormLayout row.
            parent = widget.parent()
            from PyQt5.QtWidgets import QFormLayout  # type: ignore

            if hasattr(parent, "layout"):
                layout = parent.layout()
                if isinstance(layout, QFormLayout):
                    label = layout.labelForField(widget)
                    if label is not None and hasattr(label, "setVisible"):
                        label.setVisible(True)
        except Exception:
            pass

    def hide(self, field_id: str) -> None:  # noqa: D401 (UIAdapter)
        widget = self._get_field_widget(field_id)
        if widget is None:
            return
        try:
            widget.setVisible(False)
            # Also hide the label when the widget lives in a QFormLayout row.
            parent = widget.parent()
            from PyQt5.QtWidgets import QFormLayout  # type: ignore

            if hasattr(parent, "layout"):
                layout = parent.layout()
                if isinstance(layout, QFormLayout):
                    label = layout.labelForField(widget)
                    if label is not None and hasattr(label, "setVisible"):
                        label.setVisible(False)
        except Exception:
            pass

    def enable(self, field_id: str) -> None:  # noqa: D401 (UIAdapter)
        widget = self._get_field_widget(field_id)
        if widget is None:
            return
        try:
            widget.setEnabled(True)
        except Exception:
            pass

    def disable(self, field_id: str) -> None:  # noqa: D401 (UIAdapter)
        widget = self._get_field_widget(field_id)
        if widget is None:
            return
        try:
            widget.setEnabled(False)
        except Exception:
            pass

    def set_value(self, field_id: str, value: Any) -> None:  # noqa: D401 (UIAdapter)
        widget = self._get_field_widget(field_id)
        if widget is None:
            return
        try:
            # Checkboxes: expect a boolean
            if hasattr(widget, "setChecked") and isinstance(value, (bool, type(None))):
                widget.setChecked(bool(value))
                return
            # Spin boxes: numeric
            if hasattr(widget, "setValue") and isinstance(value, (int, float)):
                widget.setValue(value)
                return
            # Combo boxes: select by text
            if hasattr(widget, "setCurrentText"):
                widget.setCurrentText(str(value) if value is not None else "")
                return
            # Line edits: set plain text
            if hasattr(widget, "setText"):
                widget.setText(str(value) if value is not None else "")
                return
        except Exception:
            pass

    # Note: `set_options` was removed. The rule engine will update combo
    # widgets directly via a fallback when the adapter does not implement
    # `set_options`, preventing import cycles and centralising option
    # population in rules.


__all__ = ["ConfigView", "CaseConfigPage"]
