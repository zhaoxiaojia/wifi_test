"""Config page view package.

This package hosts all view-only components for the Config sidebar page:

- :class:`ConfigView` – main DUT/Execution/Stability layout.
- Script-specific helpers (e.g. switch Wi-Fi / STR widgets).
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

    These two groups are defined in ``config_stability_ui.yaml`` under the
    ``stability`` panel and are shared by all stability test cases.  The
    schema builder registers them into ``page._other_groups`` keyed by the
    section id (``\"duration_control\"`` and ``\"check_point\"``).  This helper
    simply resolves those QGroupBox instances and attaches them to the page as
    ``_duration_control_group`` and ``_check_point_group`` so that controller
    logic can compose stability layouts without duplicating lookup code.
    """
    other_groups = getattr(page, "_other_groups", None)
    if not isinstance(other_groups, dict):
        return

    setattr(page, "_duration_control_group", other_groups.get("duration_control"))
    setattr(page, "_check_point_group", other_groups.get("check_point"))


def script_field_key(case_key: str, *parts: str) -> str:
    """返回 stability 脚本字段使用的 canonical key。"""
    suffix = ".".join(parts)
    return f"stability.cases.{case_key}.{suffix}"


def create_test_switch_wifi_config_entry_from_schema(
    page: Any,
    case_key: str,
    case_path: str,
    data: Mapping[str, Any],
) -> ScriptConfigEntry:
    """为 ``test_switch_wifi`` 构建 ScriptConfigEntry（使用代码创建 Wi‑Fi 编辑区域）。"""

    section_id = f"cases.{case_key}"
    group = getattr(page, "_other_groups", {}).get(section_id)
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

    # 在脚本 group 内添加 SwitchWifiConfigPage 行（不依赖 YAML 中的 manual_entries）。
    try:
        parent = group
        layout = parent.layout()
        if not isinstance(layout, QFormLayout):
            layout = QFormLayout(parent)
            parent.setLayout(layout)

        editor = SwitchWifiConfigPage(parent)
        layout.addRow(editor)

        key_script = script_field_key(case_key, SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
        widgets[key_script] = editor
        field_widgets = getattr(page, "field_widgets", {})
        field_widgets[key_script] = editor
        alias_key = f"cases.test_switch_wifi.{SWITCH_WIFI_MANUAL_ENTRIES_FIELD}"
        field_widgets[alias_key] = editor

    except Exception as exc:
        logging.info("[DEBUG switch_wifi] failed to create SwitchWifiConfigPage row:", repr(exc))

    # Treat router_csv as CSV combo driven by shared RvR Wi‑Fi proxy
    if isinstance(router_widget, ComboBox):
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


def create_test_switch_wifi_str_config_entry_from_schema(
    page: Any,
    case_key: str,
    case_path: str,
    data: Mapping[str, Any],
) -> ScriptConfigEntry:
    """
    Build ScriptConfigEntry for the merged ``test_switch_wifi_str`` stability case.

    This combines the STR/AC relay controls from the ``test_str`` schema with the
    Wi‑Fi router/manual configuration used by ``test_switch_wifi``, stacking them
    vertically in a single two‑column stability group.
    """
    # First, create the STR/AC portion using the existing helper.
    base_entry = create_test_str_config_entry_from_schema(page, case_key, case_path, data)
    group = base_entry.group
    widgets: dict[str, QWidget] = dict(base_entry.widgets)
    section_controls = dict(base_entry.section_controls)

    # Then, extend the same group with switch‑Wi‑Fi controls.
    section_id = f"cases.{case_key}"
    field_widgets = getattr(page, "field_widgets", {})

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

    # Insert SwitchWifiConfigPage as manual_entries editor at the bottom of the group.
    try:
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
        # Backwards compatible aliases using the legacy case key in dotted form.
        alias_prefix = "cases.test_switch_wifi."
        field_widgets[f"{alias_prefix}{SWITCH_WIFI_MANUAL_ENTRIES_FIELD}"] = editor
        if use_router_widget is not None:
            field_widgets[f"{alias_prefix}{SWITCH_WIFI_USE_ROUTER_FIELD}"] = use_router_widget
        if router_widget is not None:
            field_widgets[f"{alias_prefix}{SWITCH_WIFI_ROUTER_CSV_FIELD}"] = router_widget

    except Exception as exc:  # pragma: no cover - debug only
        import logging

        logging.info("[DEBUG switch_wifi_str] failed to extend group:", repr(exc))

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
    """初始化所有 stability ScriptConfigEntry（包括 switch_wifi / test_str 等脚本）。"""
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

        # 针对 switch_wifi，把 manual_entries 映射到 SwitchWifiConfigPage 实例上。
        if case_key in ("test_switch_wifi", "switch_wifi"):
            key_manual = script_field_key(case_key, SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
            manual_widget = entry.widgets.get(key_manual)
            if not isinstance(manual_widget, SwitchWifiConfigPage):
                editor = None
                if isinstance(entry.group, QWidget):
                    editors = entry.group.findChildren(SwitchWifiConfigPage)
                    editor = editors[0] if editors else None
                if editor is not None:
                    entry.widgets[key_manual] = editor
                    field_widgets = getattr(page, "field_widgets", {})
                    field_widgets[key_manual] = editor
                    alias_key = f"cases.test_switch_wifi.{SWITCH_WIFI_MANUAL_ENTRIES_FIELD}"
                    field_widgets[alias_key] = editor

        entry.group.setVisible(False)
        page._script_groups[case_key] = entry
        page.field_widgets.update(entry.widgets)
        if case_key in ("test_switch_wifi", "switch_wifi"):
            key_manual = script_field_key(case_key, SWITCH_WIFI_MANUAL_ENTRIES_FIELD)
            manual_widget = entry.widgets.get(key_manual)

    # On first load, only show shared stability groups so script-specific
    # panels don't pile up before a testcase is selected.
    stability_panel = getattr(page, "_stability_panel", None)
    if stability_panel is not None and hasattr(stability_panel, "set_groups"):
        shared_groups: list[QGroupBox] = []
        duration_group = getattr(page, "_duration_control_group", None)
        check_point_group = getattr(page, "_check_point_group", None)
        if isinstance(duration_group, QGroupBox):
            shared_groups.append(duration_group)
        if isinstance(check_point_group, QGroupBox):
            shared_groups.append(check_point_group)
        other_groups = getattr(page, "_other_groups", None)
        if isinstance(other_groups, dict):
            selected_group = other_groups.get("stability_text_case")
            if isinstance(selected_group, QGroupBox):
                shared_groups.append(selected_group)
        stability_panel.set_groups(shared_groups)


def compose_stability_groups(page: Any, active_entry: ScriptConfigEntry | None) -> list[QGroupBox]:
    """Combine shared stability controls with the active script group.

    """
    groups: list[QGroupBox] = []
    script_group: QGroupBox | None = None
    if isinstance(active_entry, ScriptConfigEntry) and isinstance(active_entry.group, QGroupBox):
        script_group = active_entry.group
    # Shared Duration / Check Point groups.
    duration_group = getattr(page, "_duration_control_group", None)
    if isinstance(duration_group, QGroupBox):
        groups.append(duration_group)
    check_point_group = getattr(page, "_check_point_group", None)
    if isinstance(check_point_group, QGroupBox):
        groups.append(check_point_group)
    # Optional \"Selected Test Case\" group defined in the stability UI schema.
    other_groups = getattr(page, "_other_groups", None)
    if isinstance(other_groups, dict):
        selected_group = other_groups.get("stability_text_case")
        if isinstance(selected_group, QGroupBox):
            groups.append(selected_group)
    # Active script-specific group (e.g. test_str / test_switch_wifi) 始终放在列表第一位，
    # 这样在两列布局中会固定在左侧列，右侧列用于 Duration/Check/Selected。
    if script_group is not None:
        if script_group in groups:
            groups.remove(script_group)
        groups.insert(0, script_group)
        # Debug: log group ordering for switch_wifi.
        if getattr(active_entry, "case_key", "") in ("test_switch_wifi", "switch_wifi"):
            try:
                titles = [g.title() for g in groups]
            except Exception:
                titles = ["<error>"]
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
