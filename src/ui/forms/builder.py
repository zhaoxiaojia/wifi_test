"""Schema-driven form builder utilities for modular UI sections."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from qfluentwidgets import ComboBox, LineEdit

WidgetFactory = Callable[["FieldSchema", QWidget], QWidget]


@dataclass(slots=True)
class FieldSchema:
    """Describe a single form field for the schema builder."""

    name: str
    label: str
    widget: str = "line_edit"
    default: Any = ""
    placeholder: str = ""
    choices: Sequence[tuple[str, str]] | Sequence[str] | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    step: int | float | None = None
    tooltip: str | None = None
    on_create: Callable[[QWidget], None] | None = None
    stretch: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)


class FormBuilder:
    """Utility to build Qt form widgets from declarative schemas."""

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._factories: dict[str, WidgetFactory] = {
            "line_edit": self._create_line_edit,
            "combo_box": self._create_combo_box,
            "checkbox": self._create_checkbox,
            "spin_box": self._create_spin_box,
            "double_spin_box": self._create_double_spin_box,
        }

    def build_form(
        self,
        layout: QLayout | None,
        schema: Iterable[FieldSchema],
        *,
        label_alignment: Qt.AlignmentFlag = Qt.AlignLeft,
    ) -> tuple[QWidget, dict[str, QWidget]]:
        """Create a QWidget containing controls described by ``schema``."""

        container = QWidget(self._parent)
        if layout is None:
            form_layout: QFormLayout = QFormLayout(container)
        else:
            form_layout = layout  # type: ignore[assignment]
            form_layout.setParent(container)
        if isinstance(form_layout, QFormLayout):
            form_layout.setLabelAlignment(label_alignment)
        widgets: dict[str, QWidget] = {}
        for field in schema:
            widget = self._create_widget(field, container)
            if field.tooltip:
                widget.setToolTip(field.tooltip)
            if isinstance(form_layout, QFormLayout):
                form_layout.addRow(QLabel(field.label, container), widget)
            else:
                row = QHBoxLayout()
                row.addWidget(QLabel(field.label, container))
                row.addWidget(widget, field.stretch or 1)
                form_layout.addLayout(row)
            widgets[field.name] = widget
        container.setLayout(form_layout)
        return container, widgets

    # ---- factories -----------------------------------------------------
    def _create_widget(self, field: FieldSchema, parent: QWidget) -> QWidget:
        factory = self._factories.get(field.widget)
        if factory is None:
            raise ValueError(f"Unsupported widget type: {field.widget}")
        widget = factory(field, parent)
        if field.on_create is not None:
            field.on_create(widget)
        return widget

    def _create_line_edit(self, field: FieldSchema, parent: QWidget) -> QWidget:
        edit = LineEdit(parent)
        if field.placeholder:
            edit.setPlaceholderText(field.placeholder)
        if field.default not in (None, ""):
            edit.setText(str(field.default))
        return edit

    def _create_combo_box(self, field: FieldSchema, parent: QWidget) -> QWidget:
        combo = ComboBox(parent)
        choices = field.choices or []
        if isinstance(choices, Mapping):
            iterable: Iterable[tuple[str, str]] = choices.items()
        else:
            iterable = []
            for item in choices:  # type: ignore[arg-type]
                if isinstance(item, tuple):
                    iterable = choices  # type: ignore[assignment]
                    break
            if iterable == []:
                iterable = [(str(item), str(item)) for item in choices]
        for value, label in iterable:  # type: ignore[assignment]
            combo.addItem(label, value)
        if field.default not in (None, ""):
            combo.setCurrentText(str(field.default))
        else:
            combo.setCurrentIndex(-1)
        return combo

    def _create_checkbox(self, field: FieldSchema, parent: QWidget) -> QWidget:
        checkbox = QCheckBox(parent)
        checkbox.setText(field.label)
        if isinstance(field.default, bool):
            checkbox.setChecked(field.default)
        return checkbox

    def _create_spin_box(self, field: FieldSchema, parent: QWidget) -> QWidget:
        spin = QSpinBox(parent)
        if field.minimum is not None:
            spin.setMinimum(int(field.minimum))
        if field.maximum is not None:
            spin.setMaximum(int(field.maximum))
        if field.step is not None:
            spin.setSingleStep(int(field.step))
        if isinstance(field.default, int):
            spin.setValue(field.default)
        return spin

    def _create_double_spin_box(self, field: FieldSchema, parent: QWidget) -> QWidget:
        spin = QDoubleSpinBox(parent)
        if field.minimum is not None:
            spin.setMinimum(float(field.minimum))
        if field.maximum is not None:
            spin.setMaximum(float(field.maximum))
        if field.step is not None:
            spin.setSingleStep(float(field.step))
        if isinstance(field.default, (int, float)):
            spin.setValue(float(field.default))
        return spin


__all__ = ["FieldSchema", "FormBuilder"]
