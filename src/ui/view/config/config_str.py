"""STR / script-related widgets and helpers for the Config page."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import ComboBox, LineEdit, PushButton

from src.ui.view.common import ScriptConfigEntry
from src.ui.view.config.actions import apply_config_ui_rules
from src.ui.view.config.config_switch_wifi import SwitchWifiManualEditor
from src.util.constants import (
    SWITCH_WIFI_MANUAL_ENTRIES_FIELD,
    SWITCH_WIFI_ROUTER_CSV_FIELD,
    SWITCH_WIFI_USE_ROUTER_FIELD,
)


class RfStepSegmentsWidget(QWidget):
    """
    Composite widget that allows the user to define one or more RF step segments.

    A segment consists of a start, stop and step value. The widget provides
    editable fields with sensible defaults and Add/Delete buttons to maintain a
    list of segments. A hint is shown when no segments are added, and a list
    view presents currently defined segments.
    """

    DEFAULT_SEGMENT = (0, 75, 3)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._segments: list[tuple[int, int, int]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        form = QGridLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)

        from PyQt5.QtGui import QIntValidator

        self.start_edit = LineEdit(self)
        self.start_edit.setPlaceholderText("Start (default 0)")
        self.start_edit.setValidator(QIntValidator(0, 9999, self))
        self.start_edit.setText(str(self.DEFAULT_SEGMENT[0]))

        self.stop_edit = LineEdit(self)
        self.stop_edit.setPlaceholderText("Stop (default 75)")
        self.stop_edit.setValidator(QIntValidator(0, 9999, self))
        self.stop_edit.setText(str(self.DEFAULT_SEGMENT[1]))

        self.step_edit = LineEdit(self)
        self.step_edit.setPlaceholderText("Step (default 3)")
        self.step_edit.setValidator(QIntValidator(1, 9999, self))
        self.step_edit.setText(str(self.DEFAULT_SEGMENT[2]))

        form.addWidget(QLabel("Start"), 0, 0)
        form.addWidget(self.start_edit, 0, 1)
        form.addWidget(QLabel("Stop"), 1, 0)
        form.addWidget(self.stop_edit, 1, 1)
        form.addWidget(QLabel("Step"), 2, 0)
        form.addWidget(self.step_edit, 2, 1)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        self.add_btn = PushButton("Add", self)
        self.add_btn.clicked.connect(self._on_add_segment)
        btn_row.addWidget(self.add_btn)

        self.del_btn = PushButton("Del", self)
        self.del_btn.clicked.connect(self._on_delete_segment)
        btn_row.addWidget(self.del_btn)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        hint_text = (
            "If no range is added, the default 0-75 (step 3) range is used.\n"
            "Enter start/stop/step, click Add to append, and select one then click Del to remove."
        )

        self.segment_stack = QStackedWidget(self)

        self.segment_hint = QLabel(hint_text, self)
        self.segment_hint.setWordWrap(True)
        self.segment_hint.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.segment_hint.setStyleSheet("color: #6c6c6c;")
        self.segment_hint.setContentsMargins(4, 4, 4, 4)

        self.segment_list = QListWidget(self)
        self.segment_list.setSelectionMode(QListWidget.SingleSelection)
        self.segment_list.currentRowChanged.connect(self._on_segment_selected)

        self.segment_stack.addWidget(self.segment_hint)
        self.segment_stack.addWidget(self.segment_list)
        layout.addWidget(self.segment_stack, 1)

        self._refresh_segment_list()

    def segments(self) -> list[tuple[int, int, int]]:
        """Return current RF step segments."""
        return list(self._segments)

    def set_segments(self, segments: Sequence[tuple[int, int, int]]) -> None:
        """Replace the current segments and refresh the list."""
        self._segments = [(int(a), int(b), int(c)) for a, b, c in segments]
        self._refresh_segment_list()

    def _refresh_segment_list(self) -> None:
        self.segment_list.clear()
        for start, stop, step in self._segments:
            item_text = f"{start} - {stop} (step {step})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, (start, stop, step))
            self.segment_list.addItem(item)
        if self._segments:
            self.segment_stack.setCurrentWidget(self.segment_list)
            self.segment_list.setCurrentRow(0)
        else:
            self.segment_stack.setCurrentWidget(self.segment_hint)

    def _on_segment_selected(self, index: int) -> None:
        if 0 <= index < len(self._segments):
            start, stop, step = self._segments[index]
            self.start_edit.setText(str(start))
            self.stop_edit.setText(str(stop))
            self.step_edit.setText(str(step))

    def _on_add_segment(self) -> None:
        start = self._coerce_int(self.start_edit.text(), self.DEFAULT_SEGMENT[0])
        stop = self._coerce_int(self.stop_edit.text(), self.DEFAULT_SEGMENT[1])
        step = self._coerce_int(self.step_edit.text(), self.DEFAULT_SEGMENT[2])
        if step <= 0:
            step = self.DEFAULT_SEGMENT[2]
        if stop < start:
            start, stop = stop, start
        self._segments.append((start, stop, step))
        self._refresh_segment_list()

    def _on_delete_segment(self) -> None:
        row = self.segment_list.currentRow()
        if 0 <= row < len(self._segments):
            del self._segments[row]
            self._refresh_segment_list()

    def _coerce_int(self, text: str, default: int) -> int:
        try:
            value = int(text.strip())
        except Exception:
            return default
        return max(0, value)


def bind_script_section(page: Any, checkbox: QCheckBox, controls: Sequence[QWidget]) -> None:
    """
    Bind a script-level section checkbox to rule evaluation.

    This is primarily used by the ``test_str`` stability configuration to
    toggle AC / STR sections.  The concrete enable/disable behaviour for the
    controls is defined in ``CONFIG_UI_RULES`` (rules R14/R15).  This helper
    simply re-evaluates the rules whenever the checkbox toggles so that the
    view logic stays outside the controller.
    """

    if not isinstance(checkbox, QCheckBox):
        return

    def _apply(_checked: bool) -> None:
        apply_config_ui_rules(page)

    checkbox.toggled.connect(_apply)
    # Ensure initial state honours the rules as well.
    apply_config_ui_rules(page)


def script_field_key(case_key: str, *parts: str) -> str:
    """Return the canonical dotted key used for stability script fields."""
    suffix = ".".join(parts)
    return f"stability.cases.{case_key}.{suffix}"


def create_test_switch_wifi_config_entry_from_schema(
    page: Any,
    case_key: str,
    case_path: str,
    data: Mapping[str, Any],
) -> ScriptConfigEntry:
    """Build ScriptConfigEntry for ``test_switch_wifi`` using builder widgets."""

    section_id = f"cases.{case_key}"
    group = getattr(page, "_other_groups", {}).get(section_id)
    if group is None:
        group = QWidget(page)

    widgets: dict[str, QWidget] = {}

    def _bind_field(field: str) -> QWidget | None:
        key = script_field_key(case_key, field)
        widget = page.field_widgets.get(key)
        if widget is None:
            raw_key = f"{section_id}.{field}"
            widget = page.field_widgets.get(raw_key)
            if widget is not None:
                page.field_widgets[key] = widget
        if widget is not None:
            widgets[key] = widget
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
                widgets[script_field_key(case_key, SWITCH_WIFI_MANUAL_ENTRIES_FIELD)] = editor
                manual_widget = editor

                # Row 1: Wi-Fi list table.
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
            # Layout tweaks are best-effort; fall back to schema layout on error.
            pass

    # Treat router_csv as a CSV combo driven by the shared RvR Wi-Fi proxy.
    if isinstance(router_widget, ComboBox):
        # Defer to page helper or global view helper for CSV registration.
        register_csv = getattr(page, "register_switch_wifi_csv_combo", None)
        if callable(register_csv):
            register_csv(router_widget)

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


def create_test_str_config_entry_from_schema(
    page: Any,
    case_key: str,
    case_path: str,
    data: Mapping[str, Any],
) -> ScriptConfigEntry:
    """Build ScriptConfigEntry for ``test_str`` using builder widgets."""

    section_id = f"cases.{case_key}"
    group = getattr(page, "_other_groups", {}).get(section_id)
    if group is None:
        group = QWidget(page)

    widgets: dict[str, QWidget] = {}

    def _bind_field(*parts: str) -> QWidget | None:
        key = script_field_key(case_key, *parts)
        widget = page.field_widgets.get(key)
        if widget is None:
            raw_key = f"{section_id}." + ".".join(parts)
            widget = page.field_widgets.get(raw_key)
            if widget is not None:
                page.field_widgets[key] = widget
        if widget is not None:
            widgets[key] = widget
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
        bind_script_section(page, ac_checkbox, ac_controls)
        section_controls["ac"] = (ac_checkbox, tuple(ac_controls))

    str_controls: list[QWidget] = [
        w for w in (str_on, str_off, str_port, str_mode, str_relay_type, str_relay_params) if w is not None
    ]
    if isinstance(str_checkbox, QCheckBox):
        bind_script_section(page, str_checkbox, str_controls)
        section_controls["str"] = (str_checkbox, tuple(str_controls))

    # Ensure relay-type changes also trigger rule evaluation (R15a/b).
    def _connect_relay_type(widget: QWidget | None) -> None:
        if isinstance(widget, ComboBox):
            widget.currentIndexChanged.connect(lambda *_: apply_config_ui_rules(page))

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


def initialize_script_config_groups(page: Any) -> None:
    """Initialise all stability ScriptConfigEntry objects for the given page."""
    stability_cfg = page.config.setdefault("stability", {})
    stability_cfg.setdefault("cases", {})
    page._script_groups.clear()

    factories = getattr(page, "_script_config_factories", {}) or {}
    for case_path, factory in factories.items():
        config_ctl = getattr(page, "config_ctl", None)
        if config_ctl is not None and hasattr(config_ctl, "script_case_key"):
            case_key = config_ctl.script_case_key(case_path)
        else:
            case_key = ""
        entry_config = page.config_ctl.ensure_script_case_defaults(case_key, case_path)
        entry = factory(page, case_key, case_path, entry_config)
        entry.group.setVisible(False)
        page._script_groups[case_key] = entry
        page.field_widgets.update(entry.widgets)


__all__ = [
    "RfStepSegmentsWidget",
    "bind_script_section",
    "script_field_key",
    "create_test_switch_wifi_config_entry_from_schema",
    "create_test_str_config_entry_from_schema",
    "initialize_script_config_groups",
]
