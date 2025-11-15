"""Schema‑driven UI builder helpers for views.

This module reads UI schema YAML files from ``src/ui/model/config``
and constructs Qt widgets (group boxes + field controls) for a given
page using a simple convention:

- Schema files:
    - config_dut_ui.yaml
    - config_execution_ui.yaml
    - config_stability_ui.yaml

- Structure (example):

    panels:
      dut:
        sections:
          - id: connect_type
            label: "Control Type"
            fields:
              - key: connect_type.type
                widget: combo_box
                label: "Control Type"

The builder expects a ``page`` object with:

- ``field_widgets: dict[str, QWidget]`` attribute
- ``_register_group(section_id, group, is_dut: bool)`` method
- ``_register_config_control(panel, group, field, widget)`` method

This fits the current ``CaseConfigPage`` implementation and allows us
to centralise YAML → UI construction logic while individual views keep
control over high‑level layout and any fine‑grained tweaks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

from PyQt5.QtWidgets import QCheckBox, QGroupBox, QVBoxLayout, QFormLayout, QSpinBox, QWidget, QLabel
from qfluentwidgets import ComboBox, LineEdit

from src.util.constants import get_model_config_base
from src.ui.model.options import get_field_choices
import yaml


@dataclass
class FieldSpec:
    key: str
    widget: str
    label: str
    placeholder: str | None = None
    minimum: int | None = None
    maximum: int | None = None
    choices: list[str] | None = None


def _load_yaml_schema(filename: str) -> Dict[str, Any]:
    base = get_model_config_base()
    path = base / filename
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    try:
        data = yaml.safe_load(text) or {}
    except Exception:
        return {}
    return data


def load_ui_schema(section: str) -> Dict[str, Any]:
    """Load the UI schema for the given high‑level section.

    ``section`` is one of: ``dut``, ``execution``, ``stability``.
    """
    mapping = {
        "dut": "config_dut_ui.yaml",
        "execution": "config_execution_ui.yaml",
        "stability": "config_stability_ui.yaml",
    }
    filename = mapping.get(section)
    if not filename:
        return {}
    return _load_yaml_schema(filename)


def _get_nested(config: Mapping[str, Any], dotted_key: str) -> Any:
    """Return nested value from config using dotted key (best‑effort)."""
    parts = dotted_key.split(".")
    current: Any = config
    for part in parts:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _create_widget(page: Any, spec: FieldSpec, value: Any) -> QWidget:
    """Create a Qt widget for a single field according to FieldSpec."""
    wtype = spec.widget
    if wtype == "checkbox":
        cb = QCheckBox(spec.label, page)
        cb.setChecked(bool(value))
        return cb
    if wtype in {"int", "spin"}:
        spin = QSpinBox(page)
        if spec.minimum is not None:
            spin.setMinimum(spec.minimum)
        if spec.maximum is not None:
            spin.setMaximum(spec.maximum)
        try:
            spin.setValue(int(value) if value is not None else 0)
        except Exception:
            spin.setValue(0)
        return spin
    if wtype == "combo_box":
        combo = ComboBox(page)
        # Prefer explicit choices from the schema; otherwise fall back to
        # centralised model options keyed by the field name.
        choices = spec.choices or get_field_choices(spec.key)
        if choices:
            for ch in choices:
                combo.addItem(str(ch), str(ch))
        elif value not in (None, ""):
            # No explicit choices: at least expose the config value so the user
            # sees a meaningful default.
            combo.addItem(str(value), str(value))
        if value not in (None, ""):
            combo.setCurrentText(str(value))
        else:
            # When no value is present in config, fall back to the first
            # available choice (if any) so the user sees a sensible default.
            combo.setCurrentIndex(0 if combo.count() else -1)
        return combo
    if wtype == "read_only_text":
        label = QLabel(page)
        label.setText(str(value) if value is not None else "")
        return label
    # default: line_edit
    edit = LineEdit(page)
    if spec.placeholder:
        edit.setPlaceholderText(spec.placeholder)
    if value not in (None, ""):
        edit.setText(str(value))
    return edit


def build_groups_from_schema(
    page: Any,
    config: Mapping[str, Any],
    ui_schema: Mapping[str, Any],
    panel_key: str,
) -> None:
    """Build all sections for ``panel_key`` described in ``ui_schema``.

    This does not arrange panels themselves; the caller is responsible
    for adding the returned group boxes to the appropriate panel
    widgets via ``_register_group``.
    """
    panels = ui_schema.get("panels") or {}
    panel_spec = panels.get(panel_key) or {}
    sections = panel_spec.get("sections") or []
    for section in sections:
        section_id = section.get("id") or ""
        group_label = section.get("label") or section_id or "Section"
        fields = section.get("fields") or []
        group = QGroupBox(group_label, page)
        layout = QFormLayout(group)
        for field in fields:
            key = str(field.get("key") or "").strip()
            if not key:
                continue
            widget_type = str(field.get("widget") or "line_edit")
            label_text = str(field.get("label") or key)
            placeholder = field.get("placeholder")
            minimum = field.get("minimum")
            maximum = field.get("maximum")
            choices = field.get("choices") or None
            spec = FieldSpec(
                key=key,
                widget=widget_type,
                label=label_text,
                placeholder=placeholder,
                minimum=int(minimum) if isinstance(minimum, int) else None,
                maximum=int(maximum) if isinstance(maximum, int) else None,
                choices=[str(c) for c in choices] if isinstance(choices, list) else None,
            )
            value = _get_nested(config, key)
            widget = _create_widget(page, spec, value)
            # Add to layout
            if isinstance(widget, QCheckBox) and spec.widget == "checkbox":
                layout.addRow(widget)
            else:
                layout.addRow(QLabel(label_text, page), widget)
            # Register widget in page.field_widgets and config_controls.
            # For the stability panel, expose both bare and ``stability.``-prefixed
            # keys so that rule specs can consistently reference
            # ``stability.*`` fields.
            logical_key = str(key).strip()
            page.field_widgets[logical_key] = widget
            if panel_key == "stability":
                stability_key = f"stability.{logical_key}"
                page.field_widgets[stability_key] = widget
            # panel is determined by panel_key; group is section_id; field is last part
            group_name = section_id or key.split(".")[0]
            field_name = key.split(".")[-1]
            try:
                page._register_config_control(panel_key, group_name, field_name, widget)
            except Exception:
                # During refactor we tolerate missing helpers; these can be wired later.
                pass
        try:
            # is_dut is True when panel_key == "dut"
            page._register_group(section_id or group_label, group, is_dut=(panel_key == "dut"))
        except Exception:
            # Caller can still manually place 'group' into a layout.
            pass


__all__ = ["load_ui_schema", "build_groups_from_schema"]
