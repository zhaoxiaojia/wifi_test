"""Shared UI helpers for theming, metadata parsing, and formatting."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Mapping

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPalette
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QTableView,
    QTableWidget,
    QTreeView,
    QWidget,
)

from src.util.constants import Paths


def _theme_module():
    """Return the lazily-imported theme module to avoid circular imports."""
    from . import theme as _theme  # local import to prevent cycles

    return _theme


def apply_font_and_selection(
    view: QAbstractItemView,
    family: str | None = None,
    size_px: int | None = None,
    sel_text: str | None = None,
    sel_bg: str | None = None,
    header_bg: str | None = None,
    header_fg: str | None = None,
    grid: str | None = None,
    adjust_row_height: bool = True,
    header_affects: bool = True,
) -> None:
    """Apply unified font, selection colors, and header styles to Qt views."""

    theme = _theme_module()
    family = family or theme.FONT_FAMILY
    size_px = size_px or (theme.FONT_SIZE + 2)
    sel_text = sel_text or "#A6E3FF"
    sel_bg = sel_bg or theme.BACKGROUND_COLOR
    header_bg = header_bg or "#202225"
    header_fg = header_fg or "#C9D1D9"
    grid = grid or "#2E2E2E"

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
            option.palette.setColor(QPalette.HighlightedText, self._sel_text)
            option.palette.setColor(QPalette.Highlight, self._sel_bg)

        def sizeHint(self, option, index):
            size = super().sizeHint(option, index)
            fm = QFontMetrics(self._font)
            height = max(size.height(), fm.height() + 6)
            return QSize(size.width(), height)

    view.setItemDelegate(_PatchedFontDelegate(view))

    # Row height and header font tuning
    if adjust_row_height and isinstance(view, (QTableView, QTableWidget)):
        view.resizeRowsToContents()
    if header_affects and isinstance(view, (QTableView, QTableWidget)):
        header_font = QFont(family)
        header_font.setPixelSize(max(12, size_px - 1))
        if view.horizontalHeader():
            view.horizontalHeader().setFont(header_font)
        if view.verticalHeader():
            view.verticalHeader().setFont(header_font)

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
        pass

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

    if hasattr(view, "setUniformRowHeights") and isinstance(view, QTreeView):
        view.setUniformRowHeights(False)
    view.viewport().update()


def format_log_html(message: str) -> str:
    """Return a unified HTML-formatted log string with theme colors."""

    theme = _theme_module()
    base_style = theme.STYLE_BASE
    text_color = theme.TEXT_COLOR
    colors = {
        "error": "#ff6b6b",
        "warning": "#facc15",
        "info": "#a6e3ff",
        "success": "#6ee7b7",
    }
    upper_msg = message.upper()
    for token, color in colors.items():
        if f"[{token.upper()}]" in upper_msg:
            return f"<span style='{base_style} color:{color};'>{message}</span>"
    return f"<span style='{base_style} color:{text_color};'>{message}</span>"


def latest_version_from_changelog(metadata: Mapping[str, str]) -> str:
    """Read README.md to determine the latest version entry."""

    default_version = metadata.get("version") or "Unknown"
    readme_path = Path(Paths.BASE_DIR) / "README.md"
    try:
        content = readme_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return default_version

    lines = content.splitlines()
    in_changelog = False
    latest_entry: str | None = None
    for line in lines:
        stripped = line.strip()
        if not in_changelog:
            if stripped.lower().startswith("## changelog"):
                in_changelog = True
            continue
        if stripped.startswith("## ") and not stripped.lower().startswith("## changelog"):
            break
        if stripped:
            latest_entry = stripped
            break

    if not latest_entry:
        return default_version
    match = re.search(r"(v?\\d+\\.\\d+(?:\\.\\d+)?)", latest_entry, re.IGNORECASE)
    return match.group(1) if match else latest_entry


def acknowledgements_from_readme() -> str:
    """Extract acknowledgements from README.md if the section exists."""

    readme_path = Path(Paths.BASE_DIR) / "README.md"
    try:
        content = readme_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    lines = content.splitlines()
    section_pattern = re.compile(r"^#+\\s*(authors|acknowledgements?)", re.IGNORECASE)
    ack_lines: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if section_pattern.match(stripped):
            in_section = True
            continue
        if in_section and stripped.startswith("#"):
            break
        if in_section and stripped:
            cleaned = stripped.lstrip("-•* ").strip()
            ack_lines.append(cleaned)
    return ", ".join(dict.fromkeys(ack_lines))


def normalize_data_source_label(source: str) -> str:
    """Normalize the data source string used by the About page."""

    source = source.replace("、", ", ")
    source = source.replace("，", ", ")
    source = source.replace("缓存", "Cache")
    source = source.replace("未知", "Unknown")
    source = re.sub(r"\\s*,\\s*", ", ", source)
    source = re.sub(r"\\s+", " ", source)
    return source.strip()
