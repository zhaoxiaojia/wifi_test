"""View helpers and script-specific widgets for the Config page.

This package hosts view-only components that extend the main ConfigView
with stability script groups such as ``test_switch_wifi`` and related
helpers.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from PyQt5.QtWidgets import QWidget, QGroupBox, QCheckBox, QFormLayout, QLabel
from qfluentwidgets import ComboBox

from .config_switch_wifi import SwitchWifiConfigPage
from src.ui.view.common import ConfigGroupPanel, ScriptConfigEntry, RfStepSegmentsWidget
from src.ui.controller.case_ctl import (
    _register_switch_wifi_csv_combo,
    _unregister_switch_wifi_csv_combo,
)
from src.util.constants import (
    SWITCH_WIFI_MANUAL_ENTRIES_FIELD,
    SWITCH_WIFI_ROUTER_CSV_FIELD,
    SWITCH_WIFI_USE_ROUTER_FIELD,
)
from src.ui.view.config.config_str import create_test_str_config_entry_from_schema


def init_stability_common_groups(page: Any) -> None:
    """Bind common stability groups (Duration Control / Check Point) to the page.

    The YAML-driven UI builder stores shared stability groups in
    ``page._other_groups`` keyed by their section id. This helper simply
    exposes them via dedicated attributes so that controller code can
    reference them directly.
    """
    other_groups = page._other_groups
    page._duration_control_group = other_groups.get("duration_control")
    page._check_point_group = other_groups.get("check_point")


def script_field_key(case_key: str, *parts: str) -> str:
    """Return canonical stability script field key."""
    suffix = ".".join(parts)
    return f"stability.cases.{case_key}.{suffix}"


def create_test_switch_wifi_config_entry_from_schema(
    page: Any,
    case_key: str,
    case_path: str,
    data: Mapping[str, Any],
) -> ScriptConfigEntry:
    """Create ScriptConfigEntry for ``test_switch_wifi`` using a code-driven Wi-Fi editor."""

    section_id = f"cases.{case_key}"
    group = page._other_groups.get(section_id)
    if group is None:
        group = QGroupBox(f"{case_key} Stability Case", page)

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

    parent = group
    layout = parent.layout()
    if not isinstance(layout, QFormLayout):
        layout = QFormLayout(parent)
        parent.setLayout(layout)

    editor = SwitchWifiConfigPage(parent)
    layout.addRow(editor)

    key_script = script_field_key(case_key, SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
    widgets[key_script] = editor
    field_widgets = page.field_widgets
    field_widgets[key_script] = editor
    alias_key = f"cases.test_switch_wifi.{SWITCH_WIFI_MANUAL_ENTRIES_FIELD}"
    field_widgets[alias_key] = editor

    # Treat router_csv as CSV combo driven by shared RvR Wi‑Fi proxy.
    if isinstance(router_widget, ComboBox):
        register_switch_wifi_csv_combo(page, router_widget)

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


def create_test_switch_wifi_str_config_entry_from_schema(
    page: Any,
    case_key: str,
    case_path: str,
    data: Mapping[str, Any],
) -> ScriptConfigEntry:
    """Build ScriptConfigEntry for the merged ``test_switch_wifi_str`` stability case."""

    # First, create the STR/AC portion using the existing helper.
    base_entry = create_test_str_config_entry_from_schema(page, case_key, case_path, data)
    group = base_entry.group
    widgets: dict[str, QWidget] = dict(base_entry.widgets)
    section_controls = dict(base_entry.section_controls)

    # Then extend the same group with switch‑Wi‑Fi controls.
    section_id = f"cases.{case_key}"
    field_widgets = page.field_widgets

    def _bind_field(field: str) -> QWidget | None:
        key = script_field_key(case_key, field)
        widget = field_widgets.get(key)
        if widget is None:
            raw_key = f"{section_id}.{field}"
            widget = field_widgets.get(raw_key)
            if widget is not None:
                field_widgets[key] = widget
        if widget is not None:
            widgets[key] = widget
        return widget

    use_router_widget = _bind_field(SWITCH_WIFI_USE_ROUTER_FIELD)
    router_widget = _bind_field(SWITCH_WIFI_ROUTER_CSV_FIELD)

    parent = group
    layout = parent.layout()
    if not isinstance(layout, QFormLayout):
        layout = QFormLayout(parent)
        parent.setLayout(layout)

    editor = SwitchWifiConfigPage(parent)
    layout.addRow(editor)

    key_script = script_field_key(case_key, SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
    widgets[key_script] = editor
    field_widgets[key_script] = editor

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
    """Initialise all stability ScriptConfigEntry instances (switch_wifi / test_str)."""
    stability_cfg = page.config.setdefault("stability", {})
    stability_cfg.setdefault("cases", {})
    page._script_groups.clear()

    factories = page._script_config_factories
    for case_path, factory in factories.items():
        case_key = page.config_ctl.script_case_key(case_path)
        entry_config = page.config_ctl.ensure_script_case_defaults(case_key, case_path)
        entry = factory(page, case_key, case_path, entry_config)

        entry.group.setVisible(False)
        page._script_groups[case_key] = entry
        page.field_widgets.update(entry.widgets)

    # On first load, only show shared stability groups so script-specific
    # panels do not pile up before a testcase is selected.
    stability_panel = page._stability_panel
    if stability_panel is not None:
        shared_groups: list[QGroupBox] = []
        if isinstance(page._duration_control_group, QGroupBox):
            shared_groups.append(page._duration_control_group)
        if isinstance(page._check_point_group, QGroupBox):
            shared_groups.append(page._check_point_group)
        selected_group = page._other_groups.get("stability_text_case")
        if isinstance(selected_group, QGroupBox):
            shared_groups.append(selected_group)
        stability_panel.set_groups(shared_groups)


def compose_stability_groups(page: Any, active_entry: ScriptConfigEntry | None) -> list[QGroupBox]:
    """Combine shared stability controls with the active script group."""
    groups: list[QGroupBox] = []
    script_group: QGroupBox | None = None

    if isinstance(active_entry, ScriptConfigEntry) and isinstance(active_entry.group, QGroupBox):
        script_group = active_entry.group

    # Shared Duration / Check Point groups.
    if isinstance(page._duration_control_group, QGroupBox):
        groups.append(page._duration_control_group)
    if isinstance(page._check_point_group, QGroupBox):
        groups.append(page._check_point_group)

    # Optional "Selected Test Case" group defined in the stability UI schema.
    selected_group = page._other_groups.get("stability_text_case")
    if isinstance(selected_group, QGroupBox):
        groups.append(selected_group)

    # Active script-specific group (e.g. test_str / test_switch_wifi) is always first.
    if script_group is not None:
        if script_group in groups:
            groups.remove(script_group)
        groups.insert(0, script_group)

    return groups


def register_switch_wifi_csv_combo(page: Any, combo: ComboBox) -> None:
    """Register a switch‑Wi‑Fi router CSV combo with the shared RvR proxy."""
    _register_switch_wifi_csv_combo(page, combo)


def unregister_switch_wifi_csv_combo(page: Any, combo: ComboBox) -> None:
    """Unregister a switch‑Wi‑Fi router CSV combo from the shared RvR proxy."""
    _unregister_switch_wifi_csv_combo(page, combo)


__all__ = [
    "RfStepSegmentsWidget",
    "init_stability_common_groups",
    "script_field_key",
    "create_test_switch_wifi_config_entry_from_schema",
    "create_test_switch_wifi_str_config_entry_from_schema",
    "initialize_script_config_groups",
    "compose_stability_groups",
    "register_switch_wifi_csv_combo",
    "unregister_switch_wifi_csv_combo",
]
