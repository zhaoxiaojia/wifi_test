#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: theme.py 
@time: 8/17/2025 2:27 PM 
@desc: 
'''

from PyQt5.QtGui import QFont

FONT_SIZE = 16
FONT_FAMILY = "Verdana"
TEXT_COLOR = "#fafafa"
BACKGROUND_COLOR = "#2b2b2b"
STYLE_BASE = f"font-size:{FONT_SIZE}px; font-family:{FONT_FAMILY};"
HTML_STYLE = f"{STYLE_BASE} color:{TEXT_COLOR};"
# --- 追加 import ---

from PyQt5.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QTreeView, QWidget
from PyQt5.QtGui import QFont, QFontMetrics, QColor, QPalette
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QStyle


class FixedFontDelegate(QStyledItemDelegate):
    def __init__(self, family="Verdana", size_px=16,
                 sel_text="#A6E3FF", sel_bg="#2B2B2B", parent=None):
        super().__init__(parent)
        self._font = QFont(family)
        self._font.setPixelSize(size_px)
        self._sel_text = QColor(sel_text)
        self._sel_bg = QColor(sel_bg)

    def initStyleOption(self, option: QStyleOptionViewItem, index):
        super().initStyleOption(option, index)
        # Force the font (override model/delegate changes)
        option.font = self._font

        # Force selection colors (highest priority path)
        if option.state & QStyle.State_Selected:
            pal = option.palette
            pal.setColor(QPalette.HighlightedText, self._sel_text)
            pal.setColor(QPalette.Text, self._sel_text)  # extra safety
            pal.setColor(QPalette.Highlight, self._sel_bg)  # selected background
            option.palette = pal

    def sizeHint(self, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        fm = QFontMetrics(opt.font)
        h = fm.height() + 6
        return QSize(opt.rect.width(), h)


def apply_tree_font_and_selection(tree: QTreeView,
                                  family="Verdana", size_px=19,
                                  sel_text="#A6E3FF", sel_bg="#2B2B2B"):
    tree.setItemDelegate(FixedFontDelegate(family, size_px, sel_text, sel_bg, tree))
    tree.setUniformRowHeights(False)
    # small padding for readability
    tree.setStyleSheet(tree.styleSheet() + "\nQTreeView::item { padding: 2px 6px; }")
    tree.viewport().update()


def apply_theme(widget, recursive: bool = False):
    widget.setStyleSheet(
        f"""
        {STYLE_BASE} color:{TEXT_COLOR}; background:{BACKGROUND_COLOR};
        QTreeView, QTreeView::item {{
            {STYLE_BASE}
            color:{TEXT_COLOR};
            background:{BACKGROUND_COLOR};
            font-family:  {FONT_FAMILY};
            font-size: {FONT_SIZE}pt;
        }}
        """
    )
    # 不必再 setFont，但如果你想保底也可以留着
    widget.setFont(QFont(FONT_FAMILY, FONT_SIZE))

    # 关键：viewport 也加上字体，防止只改颜色不改字体导致覆盖
    if hasattr(widget, "viewport"):
        widget.viewport().setStyleSheet(
            f"""
            {STYLE_BASE}
            color:{TEXT_COLOR}; background:{BACKGROUND_COLOR};
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE}pt;
            """
        )
    if recursive:
        for child in widget.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            apply_theme(child, True)


def format_log_html(message: str) -> str:
    """根据消息内容返回带统一主题的 HTML 字符串"""
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
