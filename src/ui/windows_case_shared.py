"""
Shared data structures, constants, and helpers for the Windows case UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any, Mapping, Sequence

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QCheckBox, QGroupBox, QLabel, QWidget

from .theme import STEP_LABEL_FONT_PIXEL_SIZE

STEP_LABEL_SPACING: Annotated[int, "Spacing in pixels between step labels in the GUI"] = 16
USE_QFLUENT_STEP_VIEW: Annotated[bool, "Whether to use the QFluent StepView component if available"] = False
GROUP_COLUMN_SPACING: Annotated[int, "Horizontal spacing between columns in grouped form layouts"] = 16
GROUP_ROW_SPACING: Annotated[int, "Vertical spacing between rows in grouped form layouts"] = 12
PAGE_CONTENT_MARGIN: Annotated[int, "Margin applied around content within pages and panels"] = 8


@dataclass
class EditableInfo:
    """
    Describe which fields within a test case can be edited by the user.
    """

    fields: set[str] = field(default_factory=set)
    enable_csv: bool = False
    enable_rvr_wifi: bool = False


@dataclass
class ScriptConfigEntry:
    """
    Aggregates widget references and metadata for a single script configuration panel.
    """

    group: QGroupBox
    widgets: dict[str, QWidget]
    field_keys: set[str]
    section_controls: dict[str, tuple[QCheckBox, Sequence[QWidget]]]
    case_key: str
    case_path: str
    extras: dict[str, Any] = field(default_factory=dict)


def create_step_font(base_font: QFont) -> QFont:
    """Return a bold font honoring the configured wizard label size."""
    font = QFont(base_font)
    if STEP_LABEL_FONT_PIXEL_SIZE > 0:
        font.setPixelSize(STEP_LABEL_FONT_PIXEL_SIZE)
    else:
        font.setPointSize(font.pointSize() or 12)
    font.setWeight(QFont.DemiBold)
    return font


def _apply_step_font(widget: QWidget) -> None:
    """Apply the wizard font styling to the widget and its child labels."""
    step_font = create_step_font(widget.font())
    widget.setFont(step_font)
    for label in widget.findChildren(QLabel):
        label.setFont(step_font)
    layout = widget.layout()
    if layout is not None:
        margins = layout.contentsMargins()
        if margins.left() == 0 and margins.top() == 0 and margins.right() == 0:
            layout.setContentsMargins(
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
                PAGE_CONTENT_MARGIN,
            )


__all__ = [
    "EditableInfo",
    "ScriptConfigEntry",
    "create_step_font",
    "_apply_step_font",
    "STEP_LABEL_SPACING",
    "USE_QFLUENT_STEP_VIEW",
    "GROUP_COLUMN_SPACING",
    "GROUP_ROW_SPACING",
    "PAGE_CONTENT_MARGIN",
]
