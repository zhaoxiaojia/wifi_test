"""STR / script-related widgets and helpers for the Config page."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import logging
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import ComboBox, LineEdit, PushButton

from src.ui.view.common import ScriptConfigEntry
from src.ui.model.rules import evaluate_all_rules


def bind_script_section(page: Any, checkbox: QCheckBox, controls: Sequence[QWidget]) -> None:
    """
    Bind a script-level section checkbox to rule evaluation.

    This is primarily used by the ``test_str`` stability configuration to
    toggle AC / STR sections.  The concrete enable/disable behaviour for the
    controls is expressed as ``SimpleRuleSpec`` entries in ``rules.py``.
    This helper simply re-evaluates the rules whenever the checkbox toggles
    so that the view logic stays outside the controller.
    """

    if not isinstance(checkbox, QCheckBox):
        return

    def _apply(_checked: bool) -> None:
        try:
            evaluate_all_rules(page, None)
        except Exception:
            pass

    checkbox.toggled.connect(_apply)
    # Ensure initial state honours the rules as well.
    try:
        evaluate_all_rules(page, None)
    except Exception:
        pass


def script_field_key(case_key: str, *parts: str) -> str:
    """Return the canonical dotted key used for stability script fields."""
    suffix = ".".join(parts)
    return f"stability.cases.{case_key}.{suffix}"


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
            widget.currentIndexChanged.connect(
                lambda *_: evaluate_all_rules(page, None)
            )

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


__all__ = [
    "bind_script_section",
    "script_field_key",
    "create_test_str_config_entry_from_schema",
]
