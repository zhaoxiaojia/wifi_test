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
STEP_LABEL_FONT_PIXEL_SIZE: Annotated[int, "Pixel size for step labels shown on wizard-like pages"] = 22

# Left-pane tree font size; base + 4 px for better readability.
CASE_TREE_FONT_SIZE_PX: Annotated[int, "Pixel size for case tree items (derived from base FONT_SIZE)"] = FONT_SIZE + 4

# Shared accent color and sizing tokens used across the UI.
ACCENT_COLOR: Annotated[str, "Brand/accent color used for highlights and active states"] = "#0067c0"
CONTROL_HEIGHT: Annotated[int, "Default control height in pixels for inputs/buttons"] = 32
ICON_SIZE: Annotated[int, "Icon size in pixels used for buttons/labels"] = 18
ICON_TEXT_SPACING: Annotated[int, "Horizontal spacing in pixels between icon and text"] = 8
LEFT_PAD: Annotated[int, "Left padding width combining icon size and spacing"] = ICON_SIZE + ICON_TEXT_SPACING

# -----------------------------------------------------------------------------
# Imports for Theming Helpers
# -----------------------------------------------------------------------------
from PyQt5.QtWidgets import (
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QAbstractItemView,
    QTreeView,
    QTableView,
    QTableWidget,
    QWidget,
    QGroupBox,
)
from PyQt5.QtGui import QFont, QFontMetrics, QColor, QPalette
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QStyle


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
    """
    Apply unified font, selection colors, and header styles for QTableView/QTreeView.

    Behavior:
        - Injects a delegate class that enforces font and selection color scheme.
        - Optionally adjusts row heights and header fonts.
        - Applies dark-theme header and grid styles.

    Args:
        view: The QAbstractItemView instance (QTableView, QTreeView, etc.).
        family: Font family.
        size_px: Font size in pixels.
        sel_text: Foreground color for selected text.
        sel_bg: Background color for selected rows.
        header_bg: Header background color.
        header_fg: Header text color.
        grid: Grid line color.
        adjust_row_height: If True, adjusts row height automatically.
        header_affects: If True, applies font changes to headers.

    Side effects:
        - Replaces the existing item delegate.
        - Updates widget stylesheets.
    """
    orig_delegate = view.itemDelegate()
    BaseCls = type(orig_delegate) if orig_delegate is not None else QStyledItemDelegate

    class _PatchedFontDelegate(BaseCls):
        """Internal delegate enforcing custom font and selection colors."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self._font = QFont(family)
            self._font.setPixelSize(size_px)
            self._sel_text = QColor(sel_text)
            self._sel_bg = QColor(sel_bg)

        def initStyleOption(self, option: QStyleOptionViewItem, index):
            super().initStyleOption(option, index)
            option.font = self._font
            if option.state & QStyle.State_Selected:
                pal = option.palette
                pal.setColor(QPalette.HighlightedText, self._sel_text)
                pal.setColor(QPalette.Text, self._sel_text)
                pal.setColor(QPalette.Highlight, self._sel_bg)
                option.palette = pal

    view.setItemDelegate(_PatchedFontDelegate(view))

    # Row height and header font tuning
    if adjust_row_height and isinstance(view, (QTableView, QTableWidget)):
        view.resizeRowsToContents()
    if header_affects and isinstance(view, (QTableView, QTableWidget)):
        hf = QFont(family)
        hf.setPixelSize(max(12, size_px - 1))
        if view.horizontalHeader():
            view.horizontalHeader().setFont(hf)
        if view.verticalHeader():
            view.verticalHeader().setFont(hf)

    # Header and corner dark theme skin
    header_qss = f"""
    QHeaderView {{ background-color: {header_bg}; }}
    QHeaderView::section {{
        background-color: {header_bg};
        color: {header_fg};
        padding: 4px 6px;
        border: 0px;
        border-right: 1px solid {grid};
        border-bottom: 1px solid {grid};
    }}
    """
    try:
        h = getattr(view, "horizontalHeader", lambda: None)()
        v = getattr(view, "verticalHeader", lambda: None)()
        if h:
            h.setStyleSheet(header_qss)
        if v:
            v.setStyleSheet(header_qss)
    except Exception:
        # Silent: theming should not crash functional flows
        pass

    # Corner section (top-left button) and grid color
    view.setStyleSheet(
        view.styleSheet()
        + f"""
        QTableCornerButton::section {{
            background-color: {header_bg};
            border: 0px;
            border-right: 1px solid {grid};
            border-bottom: 1px solid {grid};
        }}
        QTableView {{
            gridline-color: {grid};
        }}
        """
    )

    # TreeView compatibility: allow dynamic row height
    if hasattr(view, "setUniformRowHeights"):
        view.setUniformRowHeights(False)
    view.viewport().update()


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
        }}{step_label_style}
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
    """
    Return a unified HTML-formatted log string with theme colors.

    Args:
        message: Raw log message.

    Returns:
        HTML string with a themed <span> whose color is derived from level keywords.
        If no known level is present, returns a neutral span.

    Example:
        >>> format_log_html("Error: connection lost")
        "<span style='... color:red;'>Error: connection lost</span>"
    """
    base_style = "font-family: Consolas, 'Courier New', monospace;"
    upper_msg = message.upper()
    colors = {
        "ERROR": "red",
        "WARNING": "orange",
        "INFO": "blue",
    }
    for level, color in colors.items():
        if level in upper_msg:
            return f"<span style='{base_style} color:{color};'>{message}</span>"
    return f"<span style='{base_style}'>{message}</span>"
