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

FONT_SIZE = 14
FONT_FAMILY = "Verdana"
TEXT_COLOR = "#fafafa"
BACKGROUND_COLOR = "#2b2b2b"
STYLE_BASE = f"font-size:{FONT_SIZE}px; font-family:{FONT_FAMILY};"
HTML_STYLE = f"{STYLE_BASE} color:{TEXT_COLOR};"
# Shared accent colours and sizing tokens used across UI screens
ACCENT_COLOR = "#0067c0"
CONTROL_HEIGHT = 32
ICON_SIZE = 18
ICON_TEXT_SPACING = 8
LEFT_PAD = ICON_SIZE + ICON_TEXT_SPACING
# --- 追加 import ---

from PyQt5.QtWidgets import (
    QStyledItemDelegate, QStyleOptionViewItem, QAbstractItemView,
    QTreeView, QTableView, QTableWidget, QWidget, QGroupBox
)
from PyQt5.QtGui import QFont, QFontMetrics, QColor, QPalette
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QStyle


def apply_font_and_selection(view: QAbstractItemView,
                             family="Verdana", size_px=16,
                             sel_text="#A6E3FF", sel_bg="#2B2B2B",
                             header_bg="#202225", header_fg="#C9D1D9",
                             grid="#2E2E2E",
                             adjust_row_height=True, header_affects=True):
    """统一字体 & 选中配色，并把横/纵表头和 corner 也调成暗色。兼容 QFluentWidgets。"""

    # 1) 继承当前 delegate 类，保留其私有 API（如 setSelectedRows）
    orig_delegate = view.itemDelegate()
    BaseCls = type(orig_delegate) if orig_delegate is not None else QStyledItemDelegate

    class _PatchedFontDelegate(BaseCls):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._font = QFont(family);
            self._font.setPixelSize(size_px)
            self._sel_text = QColor(sel_text);
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

        # 可选：如果需要根据字体增高行高，再打开
        # def sizeHint(self, option, index):
        #     opt = QStyleOptionViewItem(option); self.initStyleOption(opt, index)
        #     fm = QFontMetrics(opt.font); return QSize(opt.rect.width(), fm.height() + 6)

    view.setItemDelegate(_PatchedFontDelegate(view))

    # 2) 行高/headers 字体（表格专有）
    if adjust_row_height and isinstance(view, (QTableView, QTableWidget)):
        view.resizeRowsToContents()
    if header_affects and isinstance(view, (QTableView, QTableWidget)):
        hf = QFont(family);
        hf.setPixelSize(max(12, size_px - 1))
        if view.horizontalHeader(): view.horizontalHeader().setFont(hf)
        if view.verticalHeader():   view.verticalHeader().setFont(hf)

    # 3) 表头 + corner 的暗色皮肤（关键修复“首行/首列发白”）
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
        if h: h.setStyleSheet(header_qss)
        if v: v.setStyleSheet(header_qss)
    except Exception:
        pass

    # 4) 左上角“拐角按钮”
    view.setStyleSheet(
        view.styleSheet() + f"""
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
    # Tree 专属：允许行高根据 sizeHint 变化
    if hasattr(view, "setUniformRowHeights"):
        view.setUniformRowHeights(False)
    view.viewport().update()


def apply_groupbox_style(
        group: QGroupBox,
        family: str = FONT_FAMILY,
        size_px: int = FONT_SIZE +3,
        title_px: int = FONT_SIZE,
) -> None:
    """统一 QGroupBox 内容及标题的字体样式"""
    group.setStyleSheet(
        f"QGroupBox{{font-size:{size_px}px;font-family:{family};}}"
        f"QGroupBox::title{{font-size:{title_px}px;font-family:{family};}}"
    )


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
