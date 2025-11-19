#!/usr/bin/env python
# encoding: utf-8
"""
Global UI theme configuration for PyQt5 / qfluentwidgets.

Responsibilities:
- Define global font, color, and spacing tokens.
- Provide helper functions to apply unified font, color, and header styles across widgets.
- Patch delegates for consistent font and selection color rendering in tables and trees.
- Apply dark theme palette to widgets recursively when required.
- Provide HTML log formatter with consistent theme colors.

Side effects:
- Modify QWidget/QAbstractItemView style sheets.
- Change palette/font of supplied widgets.
"""

from __future__ import annotations
from typing import Annotated

from PyQt5.QtGui import QFont

# -----------------------------------------------------------------------------
# Global Font and Color Constants (Annotated)
# -----------------------------------------------------------------------------

FONT_SIZE: Annotated[int, "Base font size in pixels for general UI text"] = 14
FONT_FAMILY: Annotated[str, "Primary UI font family"] = "Verdana"
TEXT_COLOR: Annotated[str, "Primary foreground color for text"] = "#fafafa"
BACKGROUND_COLOR: Annotated[str, "Primary background color for dark theme"] = "#2b2b2b"

STYLE_BASE: Annotated[str, "Base inline style snippet used in stylesheets (font-size & family)"] = (
    f"font-size:{FONT_SIZE}px; font-family:{FONT_FAMILY};"
)
HTML_STYLE: Annotated[str, "Default inline HTML style used by HTML-rendered widgets"] = (
    f"{STYLE_BASE} color:{TEXT_COLOR};"
)

# Wizard / step label font size in pixels (e.g., 'DUT Settings' tabs).
STEP_LABEL_FONT_PIXEL_SIZE: Annotated[int, "Pixel size for step labels shown on wizard-like pages"] = 24

# Left-pane tree font size; base + 4 px for better readability.
CASE_TREE_FONT_SIZE_PX: Annotated[int, "Pixel size for case tree items (derived from base FONT_SIZE)"] = FONT_SIZE + 4

# Shared accent color and sizing tokens used across the UI.
ACCENT_COLOR: Annotated[str, "Brand/accent color used for highlights and active states"] = "#0067c0"
CONTROL_HEIGHT: Annotated[int, "Default control height in pixels for inputs/buttons"] = 32
ICON_SIZE: Annotated[int, "Icon size in pixels used for buttons/labels"] = 18
ICON_TEXT_SPACING: Annotated[int, "Horizontal spacing in pixels between icon and text"] = 8
LEFT_PAD: Annotated[int, "Left padding width combining icon size and spacing"] = ICON_SIZE + ICON_TEXT_SPACING

# Switch Wi-Fi credential table palette tuned for dark theme readability.
SWITCH_WIFI_TABLE_HEADER_BG: Annotated[
    str,
    "Header background color for switch Wi-Fi credential tables",
] = "#2F5D90"
SWITCH_WIFI_TABLE_HEADER_FG: Annotated[
    str,
    "Header text color for switch Wi-Fi credential tables",
] = "#F5FAFF"
SWITCH_WIFI_TABLE_SELECTION_BG: Annotated[
    str,
    "Selection background color for switch Wi-Fi credential tables",
] = "#1F3E66"
SWITCH_WIFI_TABLE_SELECTION_FG: Annotated[
    str,
    "Selection text color for switch Wi-Fi credential tables",
] = "#E7F1FF"

# -----------------------------------------------------------------------------
# Imports for Theming Helpers
# -----------------------------------------------------------------------------
from PyQt5.QtWidgets import QAbstractItemView, QWidget, QGroupBox, QLabel
from PyQt5.QtGui import QFont, QPalette
from PyQt5.QtCore import Qt
from qfluentwidgets import PushButton
from .style import (
    apply_font_and_selection as _style_apply_font_and_selection,
    format_log_html as _style_format_log_html,
)


# -----------------------------------------------------------------------------
# Function: apply_font_and_selection
# -----------------------------------------------------------------------------
def apply_font_and_selection(
    view: QAbstractItemView,
    family: str = "Verdana",
    size_px: int = 16,
    sel_text: str = "#A6E3FF",
    sel_bg: str = "#2B2B2B",
    header_bg: str = "#202225",
    header_fg: str = "#C9D1D9",
    grid: str = "#2E2E2E",
    adjust_row_height: bool = True,
    header_affects: bool = True,
) -> None:
    """Apply unified table/tree styles via the shared style helpers."""
    return _style_apply_font_and_selection(
        view,
        family=family,
        size_px=size_px,
        sel_text=sel_text,
        sel_bg=sel_bg,
        header_bg=header_bg,
        header_fg=header_fg,
        grid=grid,
        adjust_row_height=adjust_row_height,
        header_affects=header_affects,
    )


# -----------------------------------------------------------------------------
# Function: apply_groupbox_style
# -----------------------------------------------------------------------------
def apply_groupbox_style(
    group: QGroupBox,
    family: str = FONT_FAMILY,
    size_px: int = FONT_SIZE + 3,
    title_px: int = FONT_SIZE,
) -> None:
    """
    Apply consistent font style to QGroupBox content and title.

    Args:
        group: Target QGroupBox.
        family: Font family.
        size_px: Font size for content text (px).
        title_px: Font size for title text (px).

    Side effects:
        - Updates QGroupBox stylesheet.
    """
    group.setStyleSheet(
        f"QGroupBox{{font-size:{size_px}px;font-family:{family};}}"
        f"QGroupBox::title{{font-size:{title_px}px;font-family:{family};}}"
    )


# -----------------------------------------------------------------------------
# Function: apply_theme
# -----------------------------------------------------------------------------
def apply_theme(widget, recursive: bool = False) -> None:
    """
    Apply dark theme and global font/color styles to a widget.

    Behavior:
        - Applies unified font/color style.
        - Adds special case for step label font size (wizard pages).
        - Optionally applies theme recursively to direct children.

    Args:
        widget: QWidget to apply the theme to.
        recursive: If True, applies recursively to children.

    Side effects:
        - Modifies widget stylesheet and font.
    """
    step_label_style = ""
    if STEP_LABEL_FONT_PIXEL_SIZE:
        step_label_style = (
            f" QLabel#wizardStepLabel {{ font-size:{STEP_LABEL_FONT_PIXEL_SIZE}px; }}"
        )

    widget.setStyleSheet(
        f"""
        {STYLE_BASE} color:{TEXT_COLOR}; background:{BACKGROUND_COLOR};
        QTreeView, QTreeView::item {{
            {STYLE_BASE}
            color:{TEXT_COLOR};
            background:{BACKGROUND_COLOR};
            font-family:{FONT_FAMILY};
            font-size:{FONT_SIZE}pt;
        }}
        {step_label_style}
        """
    )

    # Apply fallback font for consistency
    widget.setFont(QFont(FONT_FAMILY, FONT_SIZE))

    # Ensure viewport gets themed too
    if hasattr(widget, "viewport"):
        widget.viewport().setStyleSheet(
            f"""
            {STYLE_BASE}
            color:{TEXT_COLOR}; background:{BACKGROUND_COLOR};
            font-family:{FONT_FAMILY};
            font-size:{FONT_SIZE}pt;
            """
        )

    if recursive:
        for child in widget.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            apply_theme(child, True)


# -----------------------------------------------------------------------------
# Function: format_log_html
# -----------------------------------------------------------------------------
def format_log_html(message: str) -> str:
    """Return a unified HTML-formatted log string using shared helpers."""
    return _style_format_log_html(message)


def apply_settings_tab_label_style(label: QLabel, *, active: bool = False) -> None:
    """Apply unified style for DUT/Execution/Stability tab-like labels."""
    font = label.font() or QFont(FONT_FAMILY)
    font.setPixelSize(STEP_LABEL_FONT_PIXEL_SIZE)
    label.setFont(font)
    color = ACCENT_COLOR if active else TEXT_COLOR
    stylesheet = f"""
        QLabel {{
            padding: 6px 16px;
            color: {color};
            font-size: {STEP_LABEL_FONT_PIXEL_SIZE}px;
        }}
        """
    label.setStyleSheet(stylesheet)
