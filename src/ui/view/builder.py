"""Schema-driven UI builder helpers for config views.

This module reads UI schema YAML files from ``src/ui/model/config``
and constructs Qt widgets (group boxes + field controls) for a given
Config panel. It is used to render Basic / Performance / Stability
panels from YAML.
"""

from __future__ import annotations

import logging
import time
import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping

from PyQt5.QtWidgets import QCheckBox, QGroupBox, QFormLayout, QSpinBox, QWidget, QLabel
from qfluentwidgets import ComboBox, LineEdit

from src.util.constants import get_model_config_base, get_model_toolbar_base, TURN_TABLE_MODEL_RS232
from src.ui.model.options import get_field_choices
from src.ui.view.common import RfStepSegmentsWidget

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


def _load_yaml_schema(filename: str, *, base: Path | None = None) -> Dict[str, Any]:
    base_dir = base if base is not None else get_model_config_base()
    path = base_dir / filename
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
    """Load the UI schema for the given high-level section."""
    mapping = {
        "basic": "config_basic_ui.yaml",
        "dut": "config_basic_ui.yaml",
        "execution": "config_performance_ui.yaml",
        "stability": "config_stability_ui.yaml",
        "compatibility": "config_compatibility_ui.yaml",
    }
    if section == "toolbar":
        return _load_yaml_schema("config_toolbar_ui.yaml", base=get_model_toolbar_base())
    filename = mapping.get(section)
    if not filename:
        return {}
    return _load_yaml_schema(filename)


def build_inline_fields_from_schema(
    page: Any,
    config: Mapping[str, Any],
    ui_schema: Mapping[str, Any],
    panel_key: str,
    section_id: str,
    *,
    parent: QWidget,
) -> list[tuple[str, QWidget, str]]:
    """Build a flat list of fields for inline layouts (e.g. toolbar rows).

    Returns a list of (key, widget, label_text).
    """
    panels = ui_schema.get("panels") or {}
    panel_spec = panels.get(panel_key) or {}
    sections = panel_spec.get("sections") or []

    for section in sections:
        if str(section.get("id") or "") != section_id:
            continue
        fields = section.get("fields") or []
        built: list[tuple[str, QWidget, str]] = []
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
            built.append((key, widget, label_text))
        return built

    return []


def _get_nested(config: Mapping[str, Any], dotted_key: str) -> Any:
    """Return nested value from config using dotted key (best-effort)."""
    parts = dotted_key.split(".")
    current: Any = config
    for part in parts:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _normalize_control_token(value: str) -> str:
    """Normalise a token for use in config_controls IDs."""
    text = (str(value) or "").strip().lower()
    text = re.sub(r"[^0-9a-z]+", "_", text)
    return text.strip("_") or "x"


def _widget_suffix(widget: QWidget) -> str:
    """Return a short type suffix for ``widget`` (text/combo/check/spin/...)."""
    if isinstance(widget, ComboBox):
        return "combo"
    if isinstance(widget, LineEdit):
        return "text"
    if isinstance(widget, QCheckBox):
        return "check"
    if isinstance(widget, QSpinBox):
        return "spin"
    return "widget"


def _register_config_control(
    page: Any,
    panel: str,
    group: str,
    field: str,
    widget: QWidget,
) -> None:
    """Store a logical identifier for a Config page control on ``page``.

    The identifier follows the pattern ``config_panel_group_field_type``
    where each token is normalised to lower case and uses underscores
    instead of spaces or punctuation. The mapping is stored on
    ``page.config_controls`` when present and ignored otherwise.
    """
    controls = page.config_controls

    panel_token = _normalize_control_token(panel or "main")
    group_token = _normalize_control_token(group or panel or "group")
    field_token = _normalize_control_token(field or group or "field")
    suffix = _widget_suffix(widget)
    control_id = f"config_{panel_token}_{group_token}_{field_token}_{suffix}"

    controls[control_id] = widget


def _create_widget(page: Any, spec: FieldSpec, value: Any) -> QWidget:
    """Create a Qt widget for a single field according to FieldSpec."""
    wtype = spec.widget

    if wtype == "checkbox":
        cb = QCheckBox(spec.label, page)
        cb.setChecked(bool(value))
        return cb

    if wtype in {"int", "spin"}:
        # For third-party wait seconds we use a LineEdit to match other edits.
        if spec.key == "connect_type.third_party.wait_seconds":
            edit = LineEdit(page)
            if spec.placeholder:
                edit.setPlaceholderText(spec.placeholder)
            if value not in (None, ""):
                edit.setText(str(value))
            return edit
        spin = QSpinBox(page)
        if spec.minimum is not None:
            spin.setMinimum(spec.minimum)
        if spec.maximum is not None:
            spin.setMaximum(spec.maximum)
        spin.setValue(int(value) if value is not None else 0)
        return spin

    if wtype == "read_only_text":
        # Read-only text display, used for "Selected Test Case" groups.
        edit = LineEdit(page)
        edit.setReadOnly(True)
        # Also disable the control so it appears greyed-out and
        # clearly non-editable; the value is driven by the case tree.
        edit.setEnabled(False)
        if value not in (None, ""):
            edit.setText(str(value))
        return edit

    if wtype == "custom":
        # RF Solution step editor uses a dedicated composite widget that
        # manages start/stop/step segments with Add/Del controls.
        if spec.key == "rf_solution.step":
            widget = RfStepSegmentsWidget(page)
            widget.load_from_raw(value)
            return widget

    # Default: line edit or combo box.
    if wtype == "line_edit":
        edit = LineEdit(page)
        if spec.placeholder:
            edit.setPlaceholderText(spec.placeholder)
        if value not in (None, ""):
            edit.setText(str(value))
        return edit

    if wtype == "combo_box":
        combo = ComboBox(page)
        # Prefer explicit choices from the schema; otherwise fall back to
        # centralised model options keyed by the field name.
        choices = spec.choices or get_field_choices(spec.key)
        for choice in choices or []:
            combo.addItem(str(choice), str(choice))
        if value not in (None, ""):
            text = str(value)
            # Prefer userData matches when available; fall back to a
            # text-based lookup so that persisted values such as
            # "Android 11" or "RS232Board5" are restored correctly even
            # when ComboBox.findData does not recognise the string.
            idx = combo.findData(text)
            if idx < 0:
                idx = combo.findText(text)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            elif combo.count():
                combo.setCurrentIndex(0)
        return combo

    # Fallback: simple line edit.
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
    *,
    parent: QWidget | None = None,
) -> None:
    """Build all sections for ``panel_key`` described in ``ui_schema``."""
    panels = ui_schema.get("panels") or {}
    panel_spec = panels.get(panel_key) or {}
    sections = panel_spec.get("sections") or []

    for section in sections:
        _t_section = time.perf_counter()
        section_id = str(section.get("id") or "")
        group_label = str(section.get("label") or section_id or "Section")
        fields = section.get("fields") or []

        group_parent = parent if parent is not None else page
        group = QGroupBox(group_label, group_parent)
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

            # Special-case RF Solution model: when the schema and central
            # options do not provide explicit choices, derive them from the
            # rf_solution section of the current config so that existing
            # behaviour (model list driven by config) is preserved.
            if not choices and key == "rf_solution.model":
                rf_cfg = config.get("rf_solution")
                derived = [
                    str(model_key)
                    for model_key in rf_cfg.keys()
                    if model_key not in {"model", "step"}
                ]
                if TURN_TABLE_MODEL_RS232 not in derived:
                    derived.append(TURN_TABLE_MODEL_RS232)
                if derived:
                    choices = sorted(derived)

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

            # Add to layout.
            if isinstance(widget, QCheckBox) and spec.widget == "checkbox":
                layout.addRow(widget)
            else:
                layout.addRow(label_text, widget)

            # Register widget in page.field_widgets.
            logical_key = key
            # For the Stability panel we want the "Selected Test Case"
            # widget to use a stability-qualified key only, so that the
            # Execution panel's ``text_case`` field remains the canonical
            # mapping for load/save logic. Other stability fields keep the
            # plain key for rule lookups.
            if not (panel_key == "stability" and logical_key == "text_case"):
                page.field_widgets[logical_key] = widget
            if panel_key == "stability":
                stability_key = f"stability.{logical_key}"
                page.field_widgets[stability_key] = widget

            # Maintain config_controls mapping on the page when present.
            group_name = section_id or key.split(".")[0]
            field_name = key.split(".")[-1]
            _register_config_control(page, panel_key, group_name, field_name, widget)

        # If the parent looks like a ConfigGroupPanel, let it manage layout.
        # For Stability "cases.*" sections, defer adding to the panel; these
        # script groups are composed later (compose_stability_groups) to avoid
        # all scripts being laid out at startup.
        skip_panel_add = panel_key == "stability" and section_id.startswith("cases.")
        if parent is not None and not skip_panel_add:
            parent.add_group(group, defer=True)

        # Record the group on the page so that higher-level layout helpers
        # (e.g. stability common groups) can reference it later.
        is_basic_panel = panel_key in {"basic", "dut"}
        target = page._basic_groups if is_basic_panel else page._other_groups
        target[section_id or group_label] = group

        elapsed = time.perf_counter() - _t_section
        if elapsed >= 0.2:
            print(f"[STARTUP_TIME] build_groups_from_schema({panel_key}) section {section_id or group_label!r}: {elapsed:.3f}s")

    # Trigger a single rebalance for this panel if supported.
    if parent is not None:
        parent.request_rebalance()


__all__ = ["load_ui_schema", "build_groups_from_schema", "build_inline_fields_from_schema"]
